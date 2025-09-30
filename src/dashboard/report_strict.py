import os, requests, json, streamlit as st

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="FinNews Report (Strict)", layout="wide")
st.title("🧾 FinNews 報告 — STRICT Transformer 模式")

try:
    health = requests.get(f"{API_BASE}/health", timeout=5).json()
except Exception:
    health = {"status":"down", "transformer_loaded": False}

st.sidebar.markdown("### 服務狀態")
st.sidebar.json(health)

if not health.get("transformer_loaded"):
    st.error("模型未載入：請先訓練/下載模型並設定 MODEL_DIR，再重啟 API。")
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    news_id = st.text_input("指定 news_id（可留空）", "")
with col2:
    limit = st.number_input("最多載入 N 篇", value=50, min_value=1, max_value=200, step=5)
with col3:
    days = st.number_input("回溯天數", value=120, min_value=1, max_value=365)

if st.button("產生報告"):
    params = {"limit": int(limit), "days": int(days)}
    if news_id.strip():
        params["news_id"] = int(news_id.strip())
    r = requests.get(f"{API_BASE}/report", params=params)
    if r.status_code != 200:
        st.error(f"API 錯誤：{r.status_code} - {r.text}")
    else:
        data = r.json()
        st.success(f"載入 {data['count']} 篇")
        for item in data.get("items", []):
            with st.expander(f"news_id={item['news_id']}  |  doc_score={item['doc_score']:.3f}"):
                st.write("**文級機率**", item["doc_probs"])
                st.write("**句子數**", item["n_sents"])
                if item.get("keyphrases"):
                    st.write("**Top 關鍵詞（YAKE）**")
                    st.json(item["keyphrases"])
                if item.get("lda_topics"):
                    st.write("**主題（LDA）**")
                    st.json(item["lda_topics"])
                if item.get("entities"):
                    st.write("**實體（公司/產業）**")
                    st.json(item["entities"])
