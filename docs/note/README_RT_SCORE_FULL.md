# 即時句子打分補丁（完整）— Step 8 Dashboard

已在 `src/dashboard/app.py` 加入「⚡ 即時句子打分」區塊：
- 透過 `POST /score` 呼叫嚴格模式 Transformer 來計算句子情緒分數
- 若模型未載入，API 返回 503，介面會顯示「模型未載入」訊息
- 內建逾時（可調整）與錯誤處理，避免過度重試造成負載過高

## 使用方式
```bash
# 啟動 API（確保 Transformer Ready）
setx TRANSFORMER_READY 1
uvicorn src.app.api:app --host 0.0.0.0 --port 8000

# 啟動 Dashboard
streamlit run src/dashboard/app.py
```
在頁面最上方能看到「⚡ 即時句子打分」區塊，輸入句子後按「送出打分」即可。
```