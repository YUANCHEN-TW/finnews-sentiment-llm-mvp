# -*- coding: utf-8 -*-
"""
RAG 報告生成（Google Gemini API 版）— v1.4 Patch
- 針對 google-genai 的不同函式簽名做相容：
  1) generation_config=...
  2) config=...
  3) 無參數（使用預設）
- 仍保留舊版 google-generativeai 相容路徑
- 其他：欄位自動偵測、ENV 覆寫、不 join 模式、軟性 timeout、重試、退避、小連線池（防閃退）
"""
import os, math, datetime, time, re, concurrent.futures as futures
from typing import List, Dict, Optional, Tuple
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.config import DB_URL
from src.llm.prompt_templates import REPORT_PROMPT_TEMPLATE
from src.llm.guardrails import append_hallucination_warning_if_needed, ensure_missing_section_mark

# ---- Try new SDK (google-genai) ----
genai_new = None
try:
    from google import genai as genai_new  # pip install google-genai
except Exception:
    genai_new = None

# ---- Try legacy SDK (google-generativeai) ----
genai_legacy = None
try:
    import google.generativeai as genai_legacy  # pip install google-generativeai
except Exception:
    genai_legacy = None

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
MAX_K = int(os.environ.get("RAG_TOPK_MAX", "12"))
MAX_TOKENS = int(os.environ.get("RAG_MAX_TOKENS", "1200"))
TIMEOUT_S = int(os.environ.get("RAG_TIMEOUT_S", "60"))
RETRY = int(os.environ.get("RAG_RETRY", "2"))

SIG_TABLE = os.environ.get("SIG_TABLE", "news_doc_sentiment")
SIG_ID_COL = os.environ.get("SIG_ID_COL")
SIG_TIME_COL = os.environ.get("SIG_TIME_COL")
SIG_SCORE_COL = os.environ.get("SIG_SCORE_COL")

NEWS_TABLE = os.environ.get("NEWS_TABLE", "news")
NEWS_ID_COL = os.environ.get("NEWS_ID_COL")
NEWS_TITLE_COL = os.environ.get("NEWS_TITLE_COL")
NEWS_SOURCE_COL = os.environ.get("NEWS_SOURCE_COL")
NEWS_URL_COL = os.environ.get("NEWS_URL_COL")
NEWS_PUBTIME_COL = os.environ.get("NEWS_PUBTIME_COL")

_ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _quote_ident(ident: str) -> str:
    parts = ident.split(".")
    safe = []
    for p in parts:
        if not _ident_re.match(p):
            raise ValueError(f"不安全的識別子: {p}")
        safe.append(f"[{p}]")
    return ".".join(safe)

def _quote_column(col: str) -> str:
    if not _ident_re.match(col):
        raise ValueError(f"不安全的欄位名: {col}")
    return f"[{col}]"

def _make_engine() -> Engine:
    return create_engine(DB_URL, pool_pre_ping=True, pool_size=3, max_overflow=2, future=True)

def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def _freshness_decay(published_ts: datetime.datetime, now_ts: Optional[datetime.datetime]=None, tau_hours: float = 72.0) -> float:
    now_ts = now_ts or _now_utc()
    if published_ts.tzinfo is None:
        published_ts = published_ts.replace(tzinfo=datetime.timezone.utc)
    dt_h = max(0.0, (now_ts - published_ts).total_seconds() / 3600.0)
    return math.exp(-dt_h / max(1e-6, tau_hours))

def _table_exists(conn, table: str) -> bool:
    try:
        conn.execute(text(f"SELECT TOP 1 1 FROM {_quote_ident(table)}"))
        return True
    except Exception:
        return False

def _detect_first_existing_col(conn, table: str, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        try:
            conn.execute(text(f"SELECT TOP 1 {_quote_column(c)} FROM {_quote_ident(table)}"))
            return c
        except Exception:
            continue
    return None

def _detect_sig_schema(conn) -> Tuple[str,str,str,str]:
    tbl = SIG_TABLE
    if not _table_exists(conn, tbl):
        raise RuntimeError(f"找不到訊號表: {tbl}")
    id_col = SIG_ID_COL or _detect_first_existing_col(conn, tbl, ["news_id","id","doc_id","nid"])
    t_col  = SIG_TIME_COL or _detect_first_existing_col(conn, tbl, ["created_at","created","ts","timestamp","published_at","time"])
    s_col  = SIG_SCORE_COL or _detect_first_existing_col(conn, tbl, ["doc_score","score","sent_score","sentiment","sent"])
    if not all([id_col, t_col, s_col]):
        raise RuntimeError(f"{tbl} 無法偵測 id/time/score 欄位，請以 SIG_ID_COL / SIG_TIME_COL / SIG_SCORE_COL 覆寫")
    return tbl, id_col, t_col, s_col

def _detect_news_schema(conn) -> Optional[Tuple[str,str,str,str,str,str]]:
    tbl = NEWS_TABLE
    if not _table_exists(conn, tbl):
        return None
    id_col   = NEWS_ID_COL or _detect_first_existing_col(conn, tbl, ["news_id","id","doc_id","nid"])
    title_c  = NEWS_TITLE_COL or _detect_first_existing_col(conn, tbl, ["title","headline"])
    source_c = NEWS_SOURCE_COL or _detect_first_existing_col(conn, tbl, ["source","provider","media"])
    url_c    = NEWS_URL_COL or _detect_first_existing_col(conn, tbl, ["url","link","href"])
    pub_c    = NEWS_PUBTIME_COL or _detect_first_existing_col(conn, tbl, ["published_at","pub_time","time","ts","created_at"])
    if not id_col:
        return None
    return tbl, id_col, title_c, source_c, url_c, pub_c

def _fetch_top_news(date: str, top_k: int = 8) -> List[Dict]:
    top_k = min(MAX_K, max(1, int(top_k)))
    engine = _make_engine()
    with engine.begin() as conn:
        sig_tbl, sig_id, sig_time, sig_score = _detect_sig_schema(conn)
        news_schema = _detect_news_schema(conn)

        if news_schema:
            news_tbl, news_id, title_c, source_c, url_c, pub_c = news_schema
            q = f"""
                SELECT d.{_quote_column(sig_id)} AS sig_id,
                       d.{_quote_column(sig_score)} AS doc_score,
                       d.{_quote_column(sig_time)} AS doc_ts,
                       COALESCE(r.{_quote_column(pub_c)}, d.{_quote_column(sig_time)}) AS pub_ts,
                       r.{_quote_column(title_c)} AS title,
                       r.{_quote_column(source_c)} AS source,
                       r.{_quote_column(url_c)} AS url
                FROM {_quote_ident(sig_tbl)} d
                LEFT JOIN {_quote_ident(news_tbl)} r
                  ON r.{_quote_column(news_id)} = d.{_quote_column(sig_id)}
                WHERE CAST(d.{_quote_column(sig_time)} AS DATE) = :d
                ORDER BY d.{_quote_column(sig_id)} DESC
            """
            rows = conn.execute(text(q), {"d": date}).fetchall()
        else:
            q = f"""
                SELECT d.{_quote_column(sig_id)} AS sig_id,
                       d.{_quote_column(sig_score)} AS doc_score,
                       d.{_quote_column(sig_time)} AS doc_ts
                FROM {_quote_ident(sig_tbl)} d
                WHERE CAST(d.{_quote_column(sig_time)} AS DATE) = :d
                ORDER BY d.{_quote_column(sig_id)} DESC
            """
            rows = conn.execute(text(q), {"d": date}).fetchall()

    if not rows:
        return []

    source_weight = {}
    now_ts = _now_utc()
    out = []
    for r in rows:
        if news_schema:
            sig_id, score, doc_ts, pub_ts, title, source, url = r
        else:
            sig_id, score, doc_ts = r
            pub_ts, title, source, url = doc_ts, "", "", ""

        s_abs = abs(float(score or 0.0))
        fresh = _freshness_decay(pd.to_datetime(pub_ts).to_pydatetime(), now_ts, 72.0)
        w_src = float(source_weight.get((source or "").lower(), 1.0))
        rank = s_abs * fresh * w_src
        out = sorted(out + [{
            "news_id": int(sig_id) if str(sig_id).isdigit() else sig_id,
            "title": title or "",
            "source": source or "",
            "url": url or "",
            "doc_score": float(score or 0.0),
            "pub_ts": pd.to_datetime(pub_ts),
            "rank": rank
        }], key=lambda x: x["rank"], reverse=True)[:top_k]
    return out

def _fetch_signals(date: str) -> Dict:
    engine = _make_engine()
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT ticker, ds, mean_score, n_docs
                FROM signals_entity_daily
                WHERE ds = :d
            """), {"d": date}).fetchall()
        df = pd.DataFrame(rows, columns=["ticker","ds","mean_score","n_docs"])
        if df.empty:
            return {}
        df["abs"] = df["mean_score"].abs()
        df = df.sort_values("abs", ascending=False).head(20)
        out = [{"ticker": str(r.ticker), "mean_score": float(r.mean_score), "n_docs": int(r.n_docs)} for r in df.itertuples()]
        return {"entity_daily_top": out}
    except Exception:
        return {}

def _gen_with_new_client(prompt: str) -> str:
    """使用 google-genai (新) 的 models.generate_content，動態嘗試三種簽名"""
    client = genai_new.Client(api_key=os.environ["GEMINI_API_KEY"])
    contents = [{"role":"user","parts":[{"text": prompt}]}]

    # 1) generation_config=...
    try:
        resp = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=contents,
            generation_config={"temperature": 0.2, "max_output_tokens": MAX_TOKENS},
        )
        if hasattr(resp, "text") and resp.text: return resp.text
        if hasattr(resp, "candidates") and resp.candidates:
            return resp.candidates[0]["content"]["parts"][0]["text"]
    except TypeError:
        pass

    # 2) config=...
    try:
        resp = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=contents,
            config={"temperature": 0.2, "max_output_tokens": MAX_TOKENS},
        )
        if hasattr(resp, "text") and resp.text: return resp.text
        if hasattr(resp, "candidates") and resp.candidates:
            return resp.candidates[0]["content"]["parts"][0]["text"]
    except TypeError:
        pass

    # 3) 最小簽名（使用預設）
    resp = client.models.generate_content(model=DEFAULT_MODEL, contents=contents)
    if hasattr(resp, "text") and resp.text: return resp.text
    if hasattr(resp, "candidates") and resp.candidates:
        return resp.candidates[0]["content"]["parts"][0]["text"]
    raise RuntimeError("Gemini 回傳空內容")

def _gen_with_legacy_model(prompt: str) -> str:
    """使用 google-generativeai (舊) 的 GenerativeModel"""
    genai_legacy.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai_legacy.GenerativeModel(DEFAULT_MODEL)
    resp = model.generate_content(prompt, generation_config={"temperature": 0.2, "max_output_tokens": MAX_TOKENS})
    if hasattr(resp, "text") and resp.text:
        return resp.text
    return resp.candidates[0]["content"]["parts"][0]["text"]

def _call_gemini(prompt: str, timeout_s: int = TIMEOUT_S, retry: int = RETRY) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("未設定 GEMINI_API_KEY。請至 Google AI Studio 取得免費 API key，並以環境變數設定。")

    last_err = None
    for i in range(max(1, retry)):
        try:
            with futures.ThreadPoolExecutor(max_workers=1) as ex:
                if genai_new is not None:
                    fut = ex.submit(_gen_with_new_client, prompt)
                elif genai_legacy is not None:
                    fut = ex.submit(_gen_with_legacy_model, prompt)
                else:
                    raise RuntimeError("未安裝任何 Gemini SDK：請安裝 google-genai 或 google-generativeai")
                return fut.result(timeout=timeout_s)
        except Exception as e:
            last_err = e
            time.sleep(1.0 + i*0.8)
    raise last_err or RuntimeError("Gemini 生成失敗")

def _build_context(items: List[Dict]) -> str:
    lines = []
    for it in items:
        ts = pd.to_datetime(it["pub_ts"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"- {it['title']} | {it['source']} ({ts}) <{it['url']}> | 情緒強度:{abs(it['doc_score']):.2f}")
    return "\n".join(lines) if lines else "（無）"

def _build_signals_text(sig: Dict) -> str:
    if not sig:
        return "（無）"
    lines = []
    ents = sig.get("entity_daily_top", [])
    if ents:
        lines.append("【個股情緒 Top】(ticker, mean_score, n_docs)")
        for r in ents:
            lines.append(f"- {r['ticker']}: {r['mean_score']:.3f} (n={r['n_docs']})")
    return "\n".join(lines) if lines else "（無）"

def generate_daily_report(date: str, top_k: int = 8) -> str:
    top_k = min(MAX_K, max(1, int(top_k)))
    news = _fetch_top_news(date, top_k=top_k)
    sigs = _fetch_signals(date)
    ctx = _build_context(news)
    sig_text = _build_signals_text(sigs)
    prompt = REPORT_PROMPT_TEMPLATE.format(date=date, context=ctx, signals=sig_text)
    txt = _call_gemini(prompt)
    txt = ensure_missing_section_mark(txt)
    txt = append_hallucination_warning_if_needed(txt, [n.get("url","") for n in (news or [])])
    return txt