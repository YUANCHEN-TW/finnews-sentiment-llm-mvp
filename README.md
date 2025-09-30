# FinNews Sentiment + LLM 報告生成專案

## 專案簡介
這是一個 **金融新聞情緒分析 + LLM 報告生成** 專案，從新聞 ETL → NLP 前處理 → 弱監督標註 → Transformer 模型訓練 → 情緒指標建構 → 金融對齊與回測 → LLM 報告生成 → API 與 Dashboard 產品化，全流程示範一個具落地性的 AI 專案。

專案特色：
- **嚴格 Transformer 模式**：若模型未載入，API/Dashboard 會直接提示「模型未載入」，避免回退混淆。
- **防閃退機制**：所有重載/迴圈處都有防護（記憶體降載、自動回退、逾時控制）。
- **模組化**：各步驟都有獨立檔案與 CLI 指令。

---

## 步驟流程總覽

### Step 0. 測試環境
- Python 3
- Windows
- SQL Server (參照/docs/SQLServer_SETUP)
  
### Step 1. ETL（新聞擷取與儲存）
- 來源：爬取金融新聞（title, content, source, url, published_at）。
- 資料表：`news`
- 指令：
  ```bash
  python -m src.etl.fetch_news --days 30 --limit 1000
  ```

### Step 2. NLP 前處理

* 功能：中文斷句、斷詞、去除雜訊。
* 輸出：`news_doc_sentiment` 的乾淨句子。
* 指令：

  ```bash
  python -m src.etl.preprocess_news --days 30
  ```

### Step 3. 標註策略（弱監督＋人工校正）

* 基礎標註：根據情緒詞典、規則自動打標。
* 人工校正：人工抽樣檢查，形成 gold\_label。
* 指令：

  ```bash
  python -m src.etl.export_for_annotation --size 300
  ```

### Step 4. 模型訓練（Transformer）

* 使用模型：`hfl/chinese-bert-wwm-ext` 或 FinBERT。
* 相容處理：`evaluation_strategy` / `eval_strategy` 自動偵測。
* 指令（含防閃退）：

  ```bash
  python -m src.models.train_transformer \
    --model_name hfl/chinese-bert-wwm-ext \
    --epochs 1 --batch_size 4 --fp16 \
    --auto_tune --mem_fraction 0.8
  ```

### Step 5. 情緒指標建構（Signal Engineering）

* 聚合：市場 / 產業 / 個股。
* 去噪：Winsorize、中位數濾波、新鮮度衰減。
* 指標：EWMA、Z-score、Surprise。
* 指令：

  ```bash
  python -m src.signals.build_signals --days 120 --limit 50000 --throttle-ms 5
  ```

### Step 6. 金融對齊與回測

* 對齊：新聞發布時間 → 交易日 T/T+1。
* 評估：IC / RankIC、命中率、事件研究。
* 指令：

  ```bash
  python -m src.backtest.align_and_backtest \
    --start 2024-01-01 --end 2025-01-01 --cutoff 2024-12-31
  ```

### Step 7. LLM 報告生成（RAG + Guardrails）

* 檢索：Top-K 新聞，排序依 (權威 × 新鮮 × 情緒強度)。
* 模板化：市場總結 → 產業 → 個股 → 風險。
* 防幻覺：數字與引用必須來自檢索內容；無資料則輸出「無足夠信息」。
* 指令：

  ```bash
  curl "http://127.0.0.1:8000/report?date_str=2024-09-08&top_k=8"
  ```

### Step 8. API 與 Dashboard

* **API (FastAPI)**

  * `/score`：即時句子打分
  * `/index/{date}`：輸出日情緒指標
  * `/report/{date}`：生成日報

  ```bash
  uvicorn src.app.api:app --host 0.0.0.0 --port 8000
  ```

* **Dashboard (Streamlit)**

  * 功能：情緒走勢圖、驚奇度尖峰、Top News、即時句子打分、日報下載。

  ```bash
  streamlit run src/dashboard/app.py
  ```

---

## 注意事項

1. **SQL Server 相容性**

   * 部分 SQL 語法需調整（GETUTCDATE, OFFSET/TOP 不可同時使用）。
   * 請確認 `news`、`news_doc_sentiment`、`news_entity`、`signals_entity_daily` 等表結構已建好。

2. **防閃退保護**

   * 訓練程式支援 `--mem_fraction` 與 `--auto_tune`。
   * API/Dashboard 加入逾時與錯誤捕捉。
   * 嚴格模式下，Transformer 未載入會回傳 `503`。

3. **環境變數**

   * `TRANSFORMER_READY=1`：開啟嚴格 Transformer 模式。
   * `GOOGLE_API_KEY`：若使用 Gemini API 生成報告。

---

## 未來延伸

* 加入更多新聞來源（公告、社群）。
* 增強回測（多資產、跨市比較）。
* 自動化部署（Docker + GCP Cloud Run + Cloud Scheduler）。

