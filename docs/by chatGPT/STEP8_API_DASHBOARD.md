
# Step 8 — 產品化與介面（REST API + Dashboard）

## 目的
提供 REST 服務與可視化介面：打分、Top News、日報生成與下載。

## REST API（FastAPI）
- `POST /score`：嚴格模式句級打分（Transformer 未載入 → 503）
- `GET /index/{date}?top_k=8`：回傳當日 Top-K 新聞索引（不需 Transformer）
- `GET /report/{date}?top_k=8`：呼叫 RAG 生成日報（嚴格模式保護）
- 檔案：`src/app/api.py`

**啟動**
```bash
setx TRANSFORMER_READY 1
setx GEMINI_API_KEY "<你的_API_KEY>"
uvicorn src.app.api:app --host 0.0.0.0 --port 8000
# 若機器不穩定： uvicorn ... --workers 1
```

## Dashboard（Streamlit）
- 圖表：情緒走勢（mean/weighted/ewma）、驚奇度（zscore_30）
- Top News：/index
- 一鍵日報：/report（提供 .md/.html，若安裝 pdfkit+w​khtmltopdf 亦可 PDF）
- **即時句子打分**：呼叫 `/score`，可調逾時
- 檔案：`src/dashboard/app.py`

**啟動**
```bash
# 確保 src/config.py 中 DB_URL 正確
streamlit run src/dashboard/app.py
```

## 閃退防護
- API/RAG：Top-K 上限、LLM timeout+重試+退避、DB 小連線池；
- Dashboard：查詢需選擇區間/Top-K、請求加逾時、全域 try/except；
- 建議：降低 `RAG_TOPK_MAX`、`RAG_MAX_TOKENS`，API 單工啟動。
