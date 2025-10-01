
# Step 8 — 產品化與介面（REST API + Dashboard）

## 目的
提供 REST 服務與可視化介面：打分、Top News、日報生成與下載。

## 相關程式碼（重點）
- `src/app/api.py`：FastAPI：/score、/index/{date}、/report/{date}
- `src/dashboard/app.py `：Streamlit 儀表板：走勢、驚奇度、Top News、一鍵日報下載

## **REST API（FastAPI）**
* `POST /score`：嚴格模式下用 Transformer 打分（沒載入→503「模型未載入」）
* `GET /index/{date}?top_k=8`：回傳當日 Top-K 新聞索引（權威×新鮮×情緒）
* `GET /report/{date}?top_k=8`：產生日報（內部呼叫 Gemini RAG；嚴格模式保護）

## **Dashboard（Streamlit）**
* 圖表：市場/產業/個股情緒走勢（mean/weighted/ewma）、**驚奇度**（zscore_30）
* **Top News** 查詢、**一鍵產生日報並下載**（Markdown、HTML；若安裝 pdfkit+wkhtmltopdf 也可 PDF）
* **即時句子打分**：呼叫 `/score`，可調逾時


## 使用方式（指令）
```bash
# 嚴格模式：只有 Transformer 載入時才允許 /score 與 /report
setx TRANSFORMER_READY 1

# 使用 Gemini（免費層可用；之前已設過）
setx GEMINI_API_KEY "<你的_API_KEY>"

# 啟動 API
uvicorn src.app.api:app --host 0.0.0.0 --port 8000

# 另開一個終端啟動 Dashboard
streamlit run src/dashboard/app.py
```

### 防「閃退關機」的保護（已內建，仍請注意）

* **Top-K 上限**（預設 12，可用 `RAG_TOPK_MAX` 調小，例如 6）。
* **LLM 呼叫超時與重試＋退避**，避免高頻重試造成功耗尖峰。
* **DB 小連線池**（pool_size=3, max_overflow=2）＋只查必要區間。
* Dashboard 的查詢都需選擇區間、Top-K，且有 try/except 防爆。
* 如果你的機器仍不穩定，建議：

  * 將 `RAG_MAX_TOKENS` 降到 800 或更小；
  * API 用單工：`uvicorn ... --workers 1`；
  * 減少同時操作（例如先關閉其它訓練程式）。

