
# -*- coding: utf-8 -*-
"""Strict 模式看板（Streamlit）
- 僅顯示 DB 已產生的 Signals；不做任何回退運算。
- 顯示欄位擴充：weighted_mean、surprise_src7。
- 內建安全：限制查詢範圍、分批讀取、失敗時不嘗試替代來源。
"""
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.config import DB_URL

st.set_page_config(page_title="Signals (Strict)", layout="wide")

engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=4, max_overflow=4, future=True)

st.title("📈 情緒指標（Strict）")
scope = st.selectbox("層級", ["entity", "industry", "market"])

key = None
if scope == "entity":
    key = st.text_input("Ticker（必填）", value="2330")
elif scope == "industry":
    key = st.text_input("Industry（必填）", value="半導體")

c1, c2, c3 = st.columns(3)
with c1:
    start = st.text_input("開始日期（YYYY-MM-DD）", "")
with c2:
    end = st.text_input("結束日期（YYYY-MM-DD）", "")
with c3:
    limit = st.number_input("最多筆數", min_value=100, max_value=20000, value=5000, step=100)

def fetch_df():
    where = ["1=1"]
    params = {"limit": int(limit)}
    if start:
        where.append("ds >= :start"); params["start"] = start
    if end:
        where.append("ds <= :end"); params["end"] = end

    if scope in ("entity","industry") and not key:
        st.error("Strict 模式：缺少必要條件。請輸入查詢鍵。")
        return pd.DataFrame()

    if scope == "entity":
        table = "signals_entity_daily"; where.append("ticker = :k"); params["k"] = key
    elif scope == "industry":
        table = "signals_industry_daily"; where.append("industry = :k"); params["k"] = key
    else:
        table = "signals_market_daily"

    cols = "ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7"
    sql = f"""SELECT TOP (:limit) {cols} FROM {table} WHERE {' AND '.join(where)} ORDER BY ds ASC"""
    try:
        with engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        df = pd.DataFrame([dict(r) for r in rows])
        return df
    except SQLAlchemyError as e:
        st.error(f"DB 錯誤：{e}")
        return pd.DataFrame()

if st.button("查詢", type="primary"):
    df = fetch_df()
    if df.empty:
        st.warning("沒有資料可顯示（Strict）。")
    else:
        st.dataframe(df, use_container_width=True)
        with st.expander("圖表"):
            try:
                c = st.line_chart(df.set_index("ds")[["mean_score","weighted_mean","ewma_20","zscore_30","cum30"]])
            except Exception as e:
                st.error(f"繪圖失敗：{e}")

st.caption("Strict 原則：不進行任何回退估算；若資料不存在即顯示『沒有資料』。")
