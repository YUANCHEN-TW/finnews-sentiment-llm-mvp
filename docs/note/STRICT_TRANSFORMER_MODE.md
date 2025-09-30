# 嚴格 Transformer 模式

需求：API `/score` **只允許**使用 Transformer；若未載入，直接回 503。
Dashboard 也不顯示任何分數或回退，僅提示「模型未載入」。

## 如何啟動 API（嚴格版）
```
uvicorn src.app.main_strict:app --reload
```
（預設 `STRICT_TRANSFORMER=1`，會在啟動時嘗試載入模型）

### 需要的環境變數
- `MODEL_DIR`：你的訓練輸出目錄（預設 `models/bert_sentence_cls`）
- `STRICT_TRANSFORMER`：預設 `1`。設為 `1` 時，/score 未載入模型就回 503

## 健康檢查
```
GET /health
```
回傳：
```json
{
  "status": "ok",
  "transformer_loaded": true,
  "model_dir": "models/bert_sentence_cls"
}
```

## 嚴格行為（/score）
- 若模型未載入 → **HTTP 503**，內容：`Transformer 模型未載入（STRICT 模式）`
- 若模型已載入 → 正常回傳 `pred` 與 `probs`

## Dashboard（嚴格版）
啟動：
```
streamlit run src/dashboard/app_strict.py
```
- 若 `/health` 顯示 `transformer_loaded=false`，畫面只顯示提示「模型未載入」，不會顯示任何分數或回退結果。

## 先行載入（可選）
可先手動驗證模型路徑是否可用：
```
python -m src.app.load_model --model_dir models/bert_sentence_cls
```
若成功會印出「模型已載入：<路徑>」。
