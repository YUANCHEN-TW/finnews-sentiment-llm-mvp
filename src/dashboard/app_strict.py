import os, requests, json, streamlit as st

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="FinNews Dashboard (Strict)", layout="wide")
st.title("📈 FinNews Dashboard — STRICT Transformer 模式")

# 先查健康狀態
try:
    health = requests.get(f"{API_BASE}/health", timeout=5).json()
except Exception:
    health = {"status":"down", "transformer_loaded": False}

st.sidebar.markdown("### 服務狀態")
st.sidebar.json(health)

if not health.get("transformer_loaded"):
    st.warning("⚠️ 模型未載入：請先訓練/下載並放置於 `MODEL_DIR`（預設 `models/bert_sentence_cls`），或設定環境變數 `MODEL_DIR` 後重啟 API。")
    st.stop()

# 僅在模型載入後才顯示互動元件
txt = st.text_area("輸入一句新聞句子", "台積電法說會釋出利多，訂單上修")
if st.button("送出"):
    try:
        r = requests.post(f"{API_BASE}/score", json={"text": txt})
        if r.status_code == 200:
            st.success("推論成功")
            st.json(r.json())
        else:
            st.error(f"API 錯誤：{r.status_code} - {r.text}")
    except Exception as e:
        st.error(f"連線失敗：{e}")
