
# -*- coding: utf-8 -*-
"""
Step 6：align_and_backtest 熱修補 v5（完整檔）
- 欄位/表名自動偵測 + 可覆寫：解決 news_id/時間/分數/實體欄位命名差異
- Keyset pagination（主鍵遞增）避免 SQL Server TOP+OFFSET 限制
- 價格表支援 schema 與欄位自訂（以中括號安全包裹）
- 保留 CPU-only / 分批 / 節流；對齊（T/T+1）、IC/RankIC、命中率、事件研究

使用（若你的欄位名不同，可帶參數覆寫）:
python -m src.backtest.align_and_backtest --start 2024-01-01 --end 2025-09-08 \
  --cutoff 13:30 --horizons 1,5,10 \
  --price-table dbo.daily_price --ticker-col Ticker --date-col TradeDate --price-col Close \
  --sig-table news_doc_sentiment --sig-id-col news_id --sig-time-col created_at --sig-score-col doc_score \
  --ent-table news_entity --ent-fk-col news_id --ent-json-col matched_json
"""
import argparse, json, math, os, time, datetime, re
from typing import List, Tuple, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.config import DB_URL
# --- Safe DB numeric conversion: NaN/Inf -> None (SQL NULL) ---
import math as _math
def _to_db_float(x):
    """Convert x to a finite float or None (SQL NULL)."""
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    return v if _math.isfinite(v) else None

# --- Coerce any apply() output to 1-D numeric Series (drop NaN) ---
import numpy as _np
import pandas as _pd
def _to_num_series(x):
    if isinstance(x, _pd.DataFrame):
        if x.shape[1] == 1:
            x = x.iloc[:, 0]
        else:
            try:
                x = x.squeeze()
            except Exception:
                x = _pd.Series(x.values.ravel())
    if isinstance(x, _pd.Series):
        s = x
    elif _np.isscalar(x):
        s = _pd.Series([x])
    else:
        s = _pd.Series(x)
    return _pd.to_numeric(s, errors='coerce').dropna()

# ---------------- 安全/效能設定 ----------------
MAX_BATCH_DOCS = 20000
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
    # 保持連線健康、限制連線池大小避免過多併發（防止機器溫度飆高 → 閃退）
    return create_engine(DB_URL, pool_pre_ping=True, pool_size=4, max_overflow=4, future=True)

# ---------------- 基礎表（若無則建） ----------------
def _ensure_tables(engine: Engine):
    with engine.begin() as conn:
        conn.execute(text("""
IF OBJECT_ID('dim_trading_calendar','U') IS NULL
BEGIN
    CREATE TABLE dim_trading_calendar (
        ds DATE PRIMARY KEY,
        is_open BIT NOT NULL DEFAULT 1
    );
END
"""))
        conn.execute(text("""
IF OBJECT_ID('bt_signal_ic','U') IS NULL
BEGIN
    CREATE TABLE bt_signal_ic (
        id INT IDENTITY(1,1) PRIMARY KEY,
        kind NVARCHAR(16) NOT NULL,
        horizon INT NOT NULL,
        fold NVARCHAR(32) NULL,
        year INT NULL,
        ic FLOAT NULL,
        ic_p FLOAT NULL,
        ric FLOAT NULL,
        ric_p FLOAT NULL,
        hitrate FLOAT NULL,
        n_days INT NULL,
        n_pairs INT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
IF OBJECT_ID('bt_event_study','U') IS NULL
BEGIN
    CREATE TABLE bt_event_study (
        id INT IDENTITY(1,1) PRIMARY KEY,
        kind NVARCHAR(16) NOT NULL,
        side NVARCHAR(8) NOT NULL,
        horizon INT NOT NULL,
        mean_ret FLOAT NULL,
        n_events INT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
IF OBJECT_ID('bt_params','U') IS NULL
BEGIN
    CREATE TABLE bt_params (
        id INT IDENTITY(1,1) PRIMARY KEY,
        params NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
"""))

# ---------------- 行事曆（若缺則以工作日近似） ----------------
def _load_calendar(engine: Engine, start: str, end: str) -> pd.DataFrame:
    with engine.begin() as conn:
        try:
            rows = conn.execute(text("""
                SELECT ds, is_open FROM dim_trading_calendar
                WHERE ds BETWEEN :start AND :end
                ORDER BY ds
            """), {"start": start, "end": end}).fetchall()
            cal = pd.DataFrame(rows, columns=['ds','is_open'])
            if not cal.empty:
                return cal
        except Exception:
            pass
    s = pd.to_datetime(start).date()
    e = pd.to_datetime(end).date()
    days = pd.date_range(s, e, freq="D")
    cal = pd.DataFrame({"ds": days, "is_open": [int(d.weekday()<5) for d in days]})
    return cal

# ---------------- 欄位偵測 ----------------
def _detect_first_existing_col(conn, table: str, candidates: list) -> Optional[str]:
    for c in candidates:
        try:
            conn.execute(text(f"SELECT TOP 1 [{c}] FROM {table}"))
            return c
        except Exception:
            continue
    return None

def _detect_news_table(conn) -> Tuple[str, str]:
    for tbl in ["news_raw", "news"]:
        try:
            conn.execute(text(f"SELECT TOP 1 1 FROM {tbl}"))
            fk = _detect_first_existing_col(conn, tbl, ["news_id","id","doc_id"])
            if fk is None:
                continue
            print(f"[INFO] 使用新聞來源表：{tbl}（FK 欄位：{fk}）")
            return tbl, fk
        except Exception:
            continue
    raise RuntimeError("找不到 news_raw 或 news 表，或缺少可用的外鍵欄位（news_id/id/doc_id）")

# ---------------- 對齊：T/T+1 ----------------
def _t_or_t1(ts: datetime.datetime, cutoff_h: int, cutoff_m: int) -> datetime.date:
    local_date = ts.date()
    if ts.hour > cutoff_h or (ts.hour == cutoff_h and ts.minute >= cutoff_m):
        return local_date + datetime.timedelta(days=1)
    else:
        return local_date

# ---------------- 迭代載入訊號（keyset） ----------------
def _iter_aligned_signals(engine: Engine, start: str, end: str, cutoff: str,
                          chunk_size: int, throttle_ms: int, min_docs: int,
                          sig_table: str, sig_id_col: Optional[str], sig_time_col: Optional[str], sig_score_col: Optional[str],
                          ent_table: str, ent_fk_col: Optional[str], ent_json_col: Optional[str]):
    cutoff_h, cutoff_m = [int(x) for x in cutoff.split(":")]
    s_dt = pd.to_datetime(start)
    e_dt = pd.to_datetime(end) + pd.Timedelta(days=1)

    with engine.begin() as conn:
        raw_table, raw_fk = _detect_news_table(conn)
        if sig_id_col is None:
            sig_id_col = _detect_first_existing_col(conn, sig_table, ["news_id","id","doc_id"])
        if sig_time_col is None:
            sig_time_col = _detect_first_existing_col(conn, sig_table, ["created_at","created","ts","timestamp","published_at"])
        if sig_score_col is None:
            sig_score_col = _detect_first_existing_col(conn, sig_table, ["doc_score","score","sent_score","sentiment"])
        if not all([sig_id_col, sig_time_col, sig_score_col]):
            raise RuntimeError(f"{sig_table} 無法偵測到必要欄位（id/time/score）；可用 --sig-id-col/--sig-time-col/--sig-score-col 覆寫。")

        if ent_fk_col is None:
            ent_fk_col = _detect_first_existing_col(conn, ent_table, ["news_id","id","doc_id"])
        if ent_json_col is None:
            ent_json_col = _detect_first_existing_col(conn, ent_table, ["matched_json","entities_json","matched","json"])
        if not all([ent_fk_col, ent_json_col]):
            print(f"[WARN] {ent_table} 缺少實體欄位，將以空清單處理。")

    q_sig_id = _quote_column(sig_id_col)
    q_sig_time = _quote_column(sig_time_col)
    q_sig_score = _quote_column(sig_score_col)
    q_sig_tbl = sig_table
    q_ent_tbl = ent_table
    q_ent_fk = _quote_column(ent_fk_col) if ent_fk_col else None
    q_ent_json = _quote_column(ent_json_col) if ent_json_col else None

    last_id = 0
    fetched_any = False
    while True:
        with engine.begin() as conn:
            base_sql = f"""
                SELECT d.{q_sig_id} AS sig_id, d.{q_sig_time} AS created_at,
                       COALESCE(r.published_at, d.{q_sig_time}) AS pub_ts,
                       d.{q_sig_score} AS doc_score
                       {', e.' + q_ent_json + ' AS matched_json' if q_ent_json else ''}
                FROM {q_sig_tbl} d
                LEFT JOIN {raw_table} r ON r.{raw_fk} = d.{q_sig_id}
                {"LEFT JOIN " + q_ent_tbl + " e ON e." + q_ent_fk + " = d." + q_sig_id if q_ent_fk else ""}
                WHERE d.{q_sig_time} >= :s AND d.{q_sig_time} < :e
                  AND d.{q_sig_id} > :last_id
                ORDER BY d.{q_sig_id} ASC
            """
            rows = conn.execute(text(base_sql), {"s": s_dt, "e": e_dt, "last_id": last_id}).fetchmany(chunk_size)
        if not rows:
            break
        fetched_any = True

        recs = []
        for sig_id, created_at, pub_ts, doc_score, *maybe_json in rows:
            last_id = max(last_id, int(sig_id))
            matched_json = maybe_json[0] if maybe_json else None
            try:
                items = json.loads(matched_json) if matched_json else []
            except Exception:
                items = []
            if not items:
                continue
            for it in items:
                tk = (it or {}).get("ticker") or ""
                if not tk:
                    continue
                ts = pd.to_datetime(pub_ts).to_pydatetime()
                al_ds = _t_or_t1(ts, cutoff_h, cutoff_m)
                recs.append((tk, al_ds, float(doc_score)))

        if recs:
            df = pd.DataFrame(recs, columns=["ticker","ds","doc_score"]).astype({"ticker":str})
            g = df.groupby(["ticker","ds"], as_index=False).agg(
    n_docs=("doc_score","size"),
    mean_score=("doc_score","mean")
)

            g = g[g["n_docs"] >= int(min_docs)]
            if not g.empty:
                yield g

        if throttle_ms > 0:
            time.sleep(throttle_ms/1000.0)

    if not fetched_any:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT ticker, ds, n_docs, mean_score FROM signals_entity_daily
                WHERE ds BETWEEN :s AND :e
            """), {"s": start, "e": end}).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["ticker","ds","n_docs","mean_score"]).astype({"ticker":str})
            yield df

# ---------------- 價格載入 ----------------
def _find_price_candidates(engine: Engine):
    sql = text("""
        SELECT t.TABLE_SCHEMA, t.TABLE_NAME, c.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
          ON t.TABLE_SCHEMA=c.TABLE_SCHEMA AND t.TABLE_NAME=c.TABLE_NAME
        WHERE t.TABLE_TYPE='BASE TABLE'
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql).fetchall()
    from collections import defaultdict
    cols = defaultdict(set)
    for sch, tbl, col in rows:
        cols[(sch, tbl)].add(col.lower())
    cands = []
    for (sch, tbl), s in cols.items():
        score = {"ticker": any(x in s for x in ["ticker","symbol","code"]), 
                 "date": any(x in s for x in ["ds","date","tradedate","trade_date"]),
                 "close": any(x in s for x in ["close","adj_close","adjclose","price","px","last"])}
        if any(score.values()):
            cands.append((f"{sch}.{tbl}", score))
    return cands

def _load_prices(engine: Engine, price_table: str, ticker_col: str, date_col: str, price_col: str,
                 start: str, end: str) -> pd.DataFrame:
    table_sql = _quote_ident(price_table)
    t_sql = _quote_column(ticker_col)
    d_sql = _quote_column(date_col)
    p_sql = _quote_column(price_col)
    sql = f"""
        SELECT {t_sql} AS ticker, CAST({d_sql} AS DATE) AS ds, {p_sql} AS px
        FROM {table_sql}
        WHERE {d_sql} BETWEEN :s AND :e
    """
    with engine.begin() as conn:
        try:
            rows = conn.execute(text(sql), {"s": start, "e": end}).fetchall()
        except Exception as e:
            cands = _find_price_candidates(engine)
            hint = "；\n也可以建立對應 VIEW，例如：\n" \
                   f"CREATE VIEW prices_daily AS SELECT {ticker_col} AS ticker, CAST({date_col} AS DATE) AS ds, {price_col} AS [close] FROM {price_table};"
            raise RuntimeError(f"載入價格表失敗：{e}\n請確認 --price-table/--ticker-col/--date-col/--price-col。\n"
                               f"可能的候選表（含欄位跡象）:\n" +
                               "\n".join([f"  - {nm}  (ticker:{sc['ticker']}, date:{sc['date']}, close:{sc['close']})" for nm, sc in cands]) +
                               f"\n{hint}")
    if not rows:
        raise RuntimeError(f"價格表 {price_table} 在 {start}~{end} 無資料；請確認參數或日期區間。")
    df = pd.DataFrame(rows, columns=["ticker","ds","px"]).astype({"ticker":str})
    return df

# ---------------- 統計計算 ----------------
def _p_value_from_r(r: float, n: int) -> float:
    try:
        from scipy.stats import t as tdist
        if pd.isna(r) or n is None or n < 3 or abs(r) >= 1.0:
            return float('nan')
        t = r * math.sqrt((n-2) / max(1e-12, (1-r*r)))
        return float(2.0 * (1 - tdist.cdf(abs(t), df=n-2)))
    except Exception:
        if pd.isna(r) or n is None or n < 4 or abs(r) >= 1.0:
            return float('nan')
        z = math.atanh(max(min(r, 0.999999), -0.999999)) * math.sqrt(n-3)
        from math import erf, sqrt
        p = 2.0 * (1.0 - 0.5*(1.0 + erf(abs(z)/math.sqrt(2))))
        return float(p)

def _calc_daily_cs_metrics(sig_df: pd.DataFrame, px_df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    out_rows = []
    px_panel = px_df.sort_values(["ticker","ds"]).copy()
    for h in horizons:
        px_panel[f"ret_fwd_{h}"] = px_panel.groupby("ticker")["px"].transform(lambda s: s.shift(-h) / s - 1.0)
        df = sig_df.merge(px_panel[["ticker","ds",f"ret_fwd_{h}"]], on=["ticker","ds"], how="left").dropna(subset=[f"ret_fwd_{h}"])
        if df.empty:
            continue
        daily = []
        for ds, g in df.groupby("ds"):
            if len(g) < 3:
                continue
            ic = float(g["mean_score"].corr(g[f"ret_fwd_{h}"]))
            ric = float(g["mean_score"].rank(pct=True).corr(g[f"ret_fwd_{h}"].rank(pct=True)))
            hit = float(((g["mean_score"] * g[f"ret_fwd_{h}"]) > 0).mean())
            daily.append((ds, ic, ric, hit, len(g)))
        if not daily:
            continue
        tmp = pd.DataFrame(daily, columns=["ds","ic","ric","hit","n_pairs"])
        out_rows.append({"horizon": h,
                         "ic": float(tmp["ic"].mean()),
                         "ic_p": _p_value_from_r(float(tmp["ic"].mean()), len(tmp)),
                         "ric": float(tmp["ric"].mean()),
                         "ric_p": _p_value_from_r(float(tmp["ric"].mean()), len(tmp)),
                         "hitrate": float(tmp["hit"].mean()),
                         "n_days": int(len(tmp)),
                         "n_pairs": int(tmp["n_pairs"].sum())})
    return pd.DataFrame(out_rows)

def _event_study(sig_df: pd.DataFrame, px_df: pd.DataFrame, horizons: List[int], pct: float) -> pd.DataFrame:
    rows = []
    px_panel = px_df.sort_values(["ticker","ds"]).copy()
    for h in horizons:
        px_panel[f"ret_fwd_{h}"] = px_panel.groupby("ticker")["px"].transform(lambda s: s.shift(-h) / s - 1.0)
        df = sig_df.merge(px_panel[["ticker","ds",f"ret_fwd_{h}"]], on=["ticker","ds"], how="left").dropna(subset=[f"ret_fwd_{h}"])
        if df.empty:
            continue
        def pick_extreme(g: pd.DataFrame, side: str):
            q = g["mean_score"].quantile(pct if side=='long' else (1-pct))
            if side == "long":
                return g[g["mean_score"] >= q][f"ret_fwd_{h}"]
            else:
                return -g[g["mean_score"] <= q][f"ret_fwd_{h}"]
        gb = df.groupby("ds")
        r_long_raw  = gb.apply(lambda g: pick_extreme(g, "long"),  include_groups=False)
        r_short_raw = gb.apply(lambda g: pick_extreme(g, "short"), include_groups=False)
        r_long  = _to_num_series(r_long_raw)
        r_short = _to_num_series(r_short_raw)
        if len(r_long)>0:
            rows.append({"side":"long","horizon":h,"mean_ret":float(r_long.mean()),"n_events":int(r_long.count())})
        if len(r_short)>0:
            rows.append({"side":"short","horizon":h,"mean_ret":float(r_short.mean()),"n_events":int(r_short.count())})
    return pd.DataFrame(rows)

# ---------------- 主流程 ----------------
def run(start: str, end: str, cutoff: str, horizons: List[int],
        price_table: str, ticker_col: str, date_col: str, price_col: str,
        sig_table: str, sig_id_col: Optional[str], sig_time_col: Optional[str], sig_score_col: Optional[str],
        ent_table: str, ent_fk_col: Optional[str], ent_json_col: Optional[str],
        market_ticker: Optional[str], percentile: float,
        chunk_size: int, throttle_ms: int, min_docs: int):
    engine = _make_engine()
    _ensure_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO bt_params(params) VALUES(:p)"), {"p": json.dumps({
            "start": start, "end": end, "cutoff": cutoff, "horizons": horizons,
            "price_table": price_table, "ticker_col": ticker_col, "date_col": date_col, "price_col": price_col,
            "sig_table": sig_table, "sig_id_col": sig_id_col, "sig_time_col": sig_time_col, "sig_score_col": sig_score_col,
            "ent_table": ent_table, "ent_fk_col": ent_fk_col, "ent_json_col": ent_json_col,
            "market_ticker": market_ticker, "percentile": percentile,
            "chunk_size": chunk_size, "throttle_ms": throttle_ms, "min_docs": min_docs
        }, ensure_ascii=False)})

    px_df = _load_prices(engine, price_table, ticker_col, date_col, price_col, start, end)

    s = pd.to_datetime(start).date()
    e = pd.to_datetime(end).date()
    years = range(s.year, e.year + 1)
    for y in years:
        st = max(datetime.date(y,1,1), s).isoformat()
        en = min(datetime.date(y,12,31), e).isoformat()
        label = f"Y{y}"
        sig_chunks = list(_iter_aligned_signals(engine, st, en, cutoff, chunk_size, throttle_ms, min_docs,
                                                sig_table, sig_id_col, sig_time_col, sig_score_col,
                                                ent_table, ent_fk_col, ent_json_col))
        if not sig_chunks:
            print(f"[{label}] 無訊號資料。跳過。"); continue
        sig_ent = pd.concat(sig_chunks, ignore_index=True).drop_duplicates(subset=['ticker','ds'])
        met_ent = _calc_daily_cs_metrics(sig_ent, px_df, horizons)
        evt_ent = _event_study(sig_ent, px_df, horizons, percentile)

        outdir = "out/backtest"; os.makedirs(outdir, exist_ok=True)
        if not met_ent.empty:  met_ent.to_csv(os.path.join(outdir, f"metrics_entity_{label}.csv"), index=False, encoding="utf-8-sig")
        if not evt_ent.empty:  evt_ent.to_csv(os.path.join(outdir, f"events_entity_{label}.csv"),  index=False, encoding="utf-8-sig")
        with engine.begin() as conn:
            for _, r in met_ent.iterrows():
                conn.execute(text("""
                    INSERT INTO bt_signal_ic(kind, horizon, fold, year, ic, ic_p, ric, ric_p, hitrate, n_days, n_pairs)
                    VALUES ('entity', :h, :f, :y, :ic, :icp, :ric, :ricp, :hit, :nd, :np)
                """), {"h": int(r["horizon"]), "f": label, "y": y, "ic": _to_db_float(r["ic"]), "icp": _to_db_float(r["ic_p"]),
                       "ric": _to_db_float(r["ric"]), "ricp": _to_db_float(r["ric_p"]), "hit": _to_db_float(r["hitrate"]),
                       "nd": int(r["n_days"]), "np": int(r["n_pairs"])})
            for _, r in evt_ent.iterrows():
                conn.execute(text("""
                    INSERT INTO bt_event_study(kind, side, horizon, mean_ret, n_events)
                    VALUES ('entity', :s, :h, :m, :n)
                """), {"s": r["side"], "h": int(r["horizon"]), "m": r["mean_ret"], "n": int(r["n_events"])})

    print("Step 6 完成。")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=str, required=True)
    ap.add_argument("--end", type=str, required=True)
    ap.add_argument("--cutoff", type=str, default="13:30", help="收盤 HH:MM；收盤後算 T+1")
    ap.add_argument("--horizons", type=str, default="1,5,10")

    # 價格表與欄位（支援 schema.table）
    ap.add_argument("--price-table", type=str, default="prices_daily")
    ap.add_argument("--ticker-col", type=str, default="ticker")
    ap.add_argument("--date-col", type=str, default="ds")
    ap.add_argument("--price-col", type=str, default="close")

    # 訊號表與欄位（可偵測，亦可手動覆寫）
    ap.add_argument("--sig-table", type=str, default="news_doc_sentiment")
    ap.add_argument("--sig-id-col", type=str, default=None)
    ap.add_argument("--sig-time-col", type=str, default=None)
    ap.add_argument("--sig-score-col", type=str, default=None)

    # 實體表與欄位（可偵測，亦可手動覆寫）
    ap.add_argument("--ent-table", type=str, default="news_entity")
    ap.add_argument("--ent-fk-col", type=str, default=None)
    ap.add_argument("--ent-json-col", type=str, default=None)

    ap.add_argument("--market-ticker", type=str, default=None)
    ap.add_argument("--percentile", type=float, default=0.95)
    ap.add_argument("--chunk-size", type=int, default=2000)
    ap.add_argument("--throttle-ms", type=int, default=0)
    ap.add_argument("--min-docs", type=int, default=1)
    args = ap.parse_args()

    horizons = [int(x) for x in args.horizons.split(",") if x.strip()]
    run(start=args.start, end=args.end, cutoff=args.cutoff, horizons=horizons,
        price_table=args.price_table, ticker_col=args.ticker_col, date_col=args.date_col, price_col=args.price_col,
        sig_table=args.sig_table, sig_id_col=args.sig_id_col, sig_time_col=args.sig_time_col, sig_score_col=args.sig_score_col,
        ent_table=args.ent_table, ent_fk_col=args.ent_fk_col, ent_json_col=args.ent_json_col,
        market_ticker=args.market_ticker, percentile=args.percentile,
        chunk_size=args.chunk_size, throttle_ms=args.throttle_ms, min_docs=args.min_docs)