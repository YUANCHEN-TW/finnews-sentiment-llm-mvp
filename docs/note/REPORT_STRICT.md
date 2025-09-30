# /report 升級（STRICT 版）

嚴格模式：**只有**當 Transformer 已載入時才提供報告；否則回 **HTTP 503**「模型未載入」。

## 啟動
```
set MODEL_DIR=models/bert_sentence_cls
uvicorn src.app.main_strict:app --reload
```

## 產出報告（API）
```
GET /report?limit=50&days=120
GET /report?news_id=12345
```
回傳內容包含：
- 文級情緒分數/機率：`doc_score`、`doc_probs`
- 事件脈絡：`keyphrases`（YAKE）、`lda_topics`（可空）
- 實體清單：`entities`（公司/產業、別名命中與次數）

> 注意：雖然報告數據來自 DB（`news_doc_sentiment`、`news_event`、`news_entity`），但嚴格模式仍要求**模型已載入**才提供服務。

## Dashboard（Streamlit）
```
streamlit run src/dashboard/report_strict.py
```
- 若模型未載入 → 頁面僅顯示「模型未載入」，沒有任何回退顯示。
- 指定 `news_id` 可看單篇；不指定則根據 `limit` 與 `days` 列出多篇。
