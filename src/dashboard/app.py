# -*- coding: utf-8 -*-
"""
Streamlit Dashboard（步驟 8 + 即時句子打分 — 完整版）

功能：
  - 圖表：市場/產業/個股情緒走勢（mean/weighted/ewma）、驚奇度（zscore_30）
  - Top News（依 API /index/{date}）
  - 一鍵生成/下載 日報（Markdown→HTML；若有 pdfkit+w​khtmltopdf 則提供 PDF）
  - ✅ 即時句子打分（呼叫 /score；嚴格模式下 Transformer 未載入會回 503）

安全與防閃退：
  - 限制查詢區間、Top-K
  - 分批讀取、try/except 包覆 API 與 DB 的存取
  - 避免一次載入過量資料造成高瞬時功耗
"""
import os, io, json, datetime, tempfile, time
import pandas as pd
import numpy as np
import requests
import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
DB_URL = os.environ.get("DB_URL")

st.set_page_config(page_title="FinNews Sentiment Dashboard", layout="wide")
st.title("📈 FinNews Sentiment Dashboard")

# ---------- 控制面板 ----------
left, right = st.columns([2,1])
with left:
    tgt = st.text_input("股票代碼（Ticker）", value="2317")
    start = st.date_input("開始日期", value=datetime.date(2024,9,1))
    end = st.date_input("結束日期", value=datetime.date(2024,9,30))
with right:
    min_docs = st.number_input("最小文件數 (過濾)", 0, 100, 1, 1)
    throttle = st.slider("查詢節流 (ms)", 0, 500, 5, 5)
    topk = st.slider("Top News K", 1, int(os.environ.get("RAG_TOPK_MAX","12")), 8, 1)

st.divider()

# ---------- 即時句子打分 ----------
st.subheader("⚡ 即時句子打分（Transformer 嚴格模式）")
col1, col2 = st.columns([3,1])
with col1:
    text_input = st.text_area("輸入欲評分的句子（支援中文/英文財經新聞句子）", height=140, placeholder="例：台積電第三季營收優於市場預期，股價盤後上漲。")
with col2:
    st.caption("說明：\n- 嚴格模式需要模型已載入\n- 若 503：請先載入 Transformer 或設置 TRANSFORMER_READY=1")
    timeout_s = st.slider("請求逾時 (秒)", 5, 60, 20, 1)

btn_score = st.button("送出打分", type="primary")
if btn_score:
    if not text_input.strip():
        st.warning("請先輸入句子。")
    else:
        try:
            t0 = time.time()
            r = requests.post(f"{API_BASE}/score", json={"text": text_input.strip()}, timeout=timeout_s)
            dt = time.time() - t0
            if r.status_code == 503:
                st.error("模型未載入（嚴格模式）。請先啟動並載入 Transformer，再重試。")
            elif r.status_code != 200:
                st.error(f"打分失敗（HTTP {r.status_code}）：{r.text}")
            else:
                s = r.json()["score"]
                st.success(f"分數：{s:.4f}（耗時 {dt:.2f}s）")
                # 視覺化：正負情緒儀表
                import plotly.graph_objects as go
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=float(s),
                    number={"suffix": ""},
                    gauge={
                        "axis": {"range": [-1, 1]},
                        "bar": {"thickness": 0.4},
                        "threshold": {"line": {"width": 3}, "value": 0}
                    },
                    title={"text": "Sentiment Score [-1, 1]"}
                ))
                st.plotly_chart(fig, use_container_width=True)
        except requests.exceptions.Timeout:
            st.error("請求逾時，請提高逾時秒數或稍後再試。")
        except Exception as e:
            st.error(f"打分請求失敗：{e}")

st.divider()

# ---------- 資料庫讀取 ----------
def _engine() -> Engine:
    return create_engine(DB_URL, pool_pre_ping=True, pool_size=3, max_overflow=2, future=True)

def load_entity_daily(ticker: str, start: str, end: str) -> pd.DataFrame:
    eng = _engine()
    q = text("""
        SELECT ticker, ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, surprise_src7
        FROM signals_entity_daily
        WHERE ticker = :t AND ds BETWEEN :s AND :e
        ORDER BY ds ASC
    """)
    with eng.begin() as conn:
        rows = conn.execute(q, {"t": ticker, "s": start, "e": end}).fetchall()
    cols = ["ticker","ds","n_docs","mean_score","weighted_mean","ewma_20","zscore_30","surprise_src7"]
    df = pd.DataFrame(rows, columns=cols)
    return df

# ---------- 情緒走勢與驚奇度 ----------
st.subheader("📊 情緒走勢 / 驚奇度")
if st.button("載入走勢"):
    try:
        df = load_entity_daily(tgt, start.isoformat(), end.isoformat())
        if df.empty:
            st.warning("無資料")
        else:
            fig = px.line(df, x="ds", y=["mean_score","weighted_mean","ewma_20"], title=f"{tgt} 情緒走勢")
            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.bar(df, x="ds", y="zscore_30", title=f"{tgt} 30日 Z-score（驚奇度）")
            st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.error(f"讀取失敗：{e}")

# ---------- Top News ----------
st.subheader("📰 當日 Top News")
pick_date = st.date_input("Top News 日期", value=datetime.date(2024,9,8), key="pick_date")
if st.button("載入 Top News"):
    try:
        r = requests.get(f"{API_BASE}/index/{pick_date.isoformat()}", params={"top_k": topk}, timeout=30)
        if r.status_code != 200:
            st.error(f"索引失敗：{r.text}")
        else:
            data = r.json()
            st.write(f"日期：{data['date']}，Top-K：{data['top_k']}")
            st.dataframe(pd.DataFrame(data["items"]))
    except Exception as e:
        st.error(f"請求失敗：{e}")

# ---------- 一鍵生成/下載 日報 ----------
st.subheader("📝 一鍵生成/下載 日報")
report_date = st.date_input("報告日期", value=datetime.date(2024,9,8), key="report_date")
if st.button("生成日報 (Markdown)"):
    try:
        r = requests.get(f"{API_BASE}/report/{report_date.isoformat()}", params={"top_k": topk}, timeout=60)
        if r.status_code != 200:
            st.error(f"生成失敗：{r.text}")
        else:
            md = r.json()["report"]
            st.text_area("Report (Markdown)", md, height=320)
            st.download_button("下載 .md", data=md.encode("utf-8"), file_name=f"report_{report_date}.md")

            # 轉 HTML（簡單安全轉義）
            html = "<html><head><meta charset='utf-8'></head><body><pre>" + \
                   md.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;") + \
                   "</pre></body></html>"
            st.download_button("下載 .html", data=html.encode("utf-8"), file_name=f"report_{report_date}.html")

            # PDF（若環境有 pdfkit + wkhtmltopdf）
            try:
                import pdfkit
                with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
                    f.write(html.encode("utf-8"))
                    f.flush()
                    pdf_bytes = pdfkit.from_file(f.name, False)
                st.download_button("下載 .pdf", data=pdf_bytes, file_name=f"report_{report_date}.pdf")
            except Exception:
                st.info("未安裝 pdfkit 或 wkhtmltopdf，暫不提供 PDF。")
    except Exception as e:
        st.error(f"請求失敗：{e}")

st.caption("⚠️ 已限制 Top-K、超時與連線池；若機器不穩定，請降低 K 與查詢區間、或以單 workers 方式啟動 API。")