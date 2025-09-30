# 金融新聞情緒分析 + LLM 報告生成（MVP 模板）

這是可直接開工的 **端到端** 專案模板：ETL → NLP → 指標聚合 → 回測 → API → Dashboard → 報告生成。  
著重「**可運行**＋**可展示**＋**可延伸**」。

# 目的（Why）

## 業務目標
* 將**每日金融新聞/公告/社群**轉成可量化的**情緒指標**（Sentiment Index），輔助投研與風控。
* 以**可回測**的方式驗證情緒對**隔日/短期報酬**與波動的解釋力，提供可視化儀表板與自動化**日報**。
* 以 **LLM 自動生成「市場摘要＋個股重點＋風險提示」**，縮短分析師資訊蒐集與寫作時間。

## 技術目標
* 建立**可重現的資料管線**（ETL→NLP→指標→回測→API→報告）。
* 完成**雙層架構**：① 情緒分類器（傳統/Transformer/FinBERT/中文BERT）；② LLM 報告生成（帶引用與防幻覺）。
* 具備**MLOps 能力**：資料版本控管、模型重訓、評估監控、容器化與雲端部署。

---

# 產出（Deliverables）
1. **Dashboard**（Streamlit/Gradio）：情緒熱度、主題、實體（公司/產業）、與股價疊圖、可回放區間。
2. **REST API**（FastAPI）：`/score`（輸入文本→情緒分數）、`/daily_index`（輸出市場/產業/個股指數）。
3. **自動日報**（LLM）：附**引用來源連結**與**關鍵數據表**（Markdown/HTML/PDF）。
4. **回測報告**：事件研究（Event Study）、信息係數（IC）、命中率（directional hit rate）、PR/AUC。
5. **完整專案倉庫**：含 README、架構圖、Dockerfile、CI/CD workflow、測試與追蹤記錄。

---

# 系統總覽
* **Data 層**：新聞RSS/網站爬取/公告/社群API → 原文儲存（含來源、時間、標的、語言）。
* **NLP 層**：清理→語言偵測→分句→關鍵實體（公司/代碼/產業）→**情緒分類器**→主題模型/關鍵詞→**情緒指標聚合**（市場/產業/個股）。
* **Quant 層**：與行情資料（收盤、隔日報酬、波動）對齊，做對齊與延遲修正（避免未來函數），回測與指標產出。
* **LLM 層**：以**模板化 Prompt** + **檢索式生成（RAG）**，生成日報，強制「引文必顯示」。
* **服務層**：FastAPI + 任務排程（每天開盤前/收盤後）＋Dashboard。
* **MLOps**：DVC/Weights & Biases（或 MLflow）追蹤資料與模型；Docker 容器；定期重訓；監控漂移。

---

# 流程規劃（含細節與檢核點）
## 0. 範圍與指標定義（MVP）
* 市場：先選 **台股大盤＋5–10 檔高流動性股票**。
* 評估重點：
  * NLP：F1（pos/neg/neu）、宏平均 F1。
  * 金融：**IC**（情緒 vs. 隔日/3日/5日收益）、**命中率**、**勝率曲線**、分組回測（Q1\~Q5 分組）。
* 報告版型：一頁式（Top News、情緒走勢、關鍵個股、風險雷達、引用）。

## 1. 資料蒐集（ETL）
* 來源：指定幾個主要新聞站/交易所公告/RSS/社群。（先 3–5 個來源作 MVP）
* 儲存：原文、標題、URL、發布時間、抓取時間、來源、可能的股票代碼（規則抽取）。
* 反爬/法遵：尊重 robots/版權；設定抓取速率與重試；去重（URL/內容指紋）。

## 2. NLP 前處理
* 中文/英文語言偵測；全形半形、標點清理；移除模板字串（免廣告/免頁尾）。
* NER/規則：抽取**公司名/股票代碼/產業關鍵詞**；多來源字典＋模糊匹配。
* 分句與時間對齊：記錄**可交易時間窗**，確保回測不使用未來資訊。

## 3. 標註策略（最小可行）
* 先用 **弱監督**：字典/情緒詞庫 + 句法規則 → 生成粗標註；抽樣做人手校正 500–1000 句。
* 迭代：以小量人工標註提升精度，作為**驗證集/測試集**；保留噪聲分析報告。

## 4. 模型層（比較與選型）
* Baseline：LogReg/SVM（tf-idf）；傳統可解釋、訓練快。
* Stronger：**中文 BERT/FinBERT 變體**微調；加入**情境增強**（同一新聞內多句聚合）。
* 主題/事件：LDA 或 keyphrase（YAKE/TextRank）做**事件脈絡**，輔助 LLM 報告摘要。
* 輸出：句級/文級**情緒分數**（連續值），並標注**實體關聯**（公司/產業）。

## 5. 情緒指標建構（Signal Engineering）
* 聚合：
  * 市場層：全市場加權平均（權重=來源權威度×新鮮度）
  * 產業層：依產業字典匯總
  * 個股層：只聚合**含該公司實體**的句子/文章
* 去噪：Winsorize/中位數濾波；**新鮮度衰減**（例如 e^(-Δt/τ)）。
* 驚奇度（Surprise）：同來源/同公司與**近7日均值差異**的 Z-score。

## 6. 金融對齊與回測
* 對齊：以**發布時間**對齊到可交易日（T、T+1），避開收盤後新聞導致的資訊洩漏。
* 指標：
  * **IC/RankIC**（情緒 vs. 未來報酬）
  * 命中率（多空方向）
  * 事件研究（公告/大利空/大利多）
* 穩健性：滾動視窗（walk-forward）、分年度/牛熊子樣本、p-value 與效應量報告。

## 7. LLM 報告生成（RAG + Guardrails）
* 檢索：以**當日 Top-K 新聞**（依權威×新鮮×情緒強度排序）餵入 LLM。
* 模板化 Prompt：
  * 段落順序固定（市場總結→產業→個股→風險）
  * **必列出引用**（新聞標題＋來源＋時間＋連結）
  * 數字必來自檢索內容或我們計算的指標（拒絕臆測）。
* 防幻覺：回答中加入「若無資料，請明確標示『無足夠信息』」。

## 8. 產品化與介面
* **REST API（FastAPI）**：`/score`, `/index/{date}`, `/report/{date}`。
* **Dashboard（Streamlit）**：
  * 圖表：市場/產業/個股情緒走勢、與報酬疊圖、驚奇度尖峰、Top News、可切換區間/標的。
  * 一鍵生成/下載**日報**（Markdown→HTML/PDF）。

## 9. MLOps 與監控
* 版本追蹤：Git + DVC/MLflow（數據/模型/參數/指標）。
* 例行任務：以 cron/Cloud Scheduler 每日抓取、計算、回測更新。
* 監控：情緒分數分佈漂移、命中率/IC 週報；異常告警（來源斷流、API 失敗）。

## 10. 安全與法遵
* 來源授權與 robots 規範；清楚標注內容歸屬。
* PII/敏感詞處理；LLM 輸出加上**免責聲明**與使用範圍。

---

# 週程與里程碑（建議 8–10 週）
**W1** … **W10**（依你原文）

---

# 驗收與展示（面試導向）
* **Demo 劇本**（5–7 分鐘）：…
* **成就數字**：…

---

# 技術棧建議
* Python、生態系套件、追蹤、儲存、容器、測試…

---

# 風險與對策
* 來源不穩／變更：…
* 中文金融語境歧義高：…
* LLM 幻覺：…
* 指標不顯著：…


## 快速開始

### 0) 建議環境
- Python 3.10+
- macOS/Linux/WSL（Windows 也可）

### 1) 建立虛擬環境並安裝
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m nltk.downloader punkt
```

### 2) 初始化資料庫與範例資料
```bash
python src/etl/demo_seed.py
```

### 3) 訓練 Baseline（TF-IDF + Logistic Regression）
```bash
python src/models/train_baseline.py
```

### 4) 啟動 REST API（FastAPI）
```bash
uvicorn src.app.main:app --reload
```
- 連到 `http://127.0.0.1:8000/docs` 查看 Swagger。

### 5) 啟動 Dashboard（Streamlit）
```bash
streamlit run src/dashboard/app.py
```
```bash
python -m streamlit run src/dashboard/app.py
```
---

## 專案結構
```
finnews-sentiment-llm-mvp/
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ .env.example
├─ Dockerfile
├─ docker-compose.yml
├─ src/
│  ├─ config.py
│  ├─ utils/
│  │  ├─ logging.py
│  │  └─ time.py
│  ├─ etl/
│  │  ├─ fetchers/rss_fetcher.py
│  │  ├─ clean.py
│  │  ├─ ner.py
│  │  ├─ label_weak.py
│  │  └─ demo_seed.py
│  ├─ models/
│  │  ├─ registry.py
│  │  ├─ train_baseline.py
│  │  ├─ train_transformer.py
│  │  └─ eval.py
│  ├─ quant/
│  │  ├─ align.py
│  │  ├─ metrics.py
│  │  └─ backtest.py
│  ├─ llm/
│  │  ├─ prompt_templates.py
│  │  ├─ rag.py
│  │  └─ generate_report.py
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py
│  │  ├─ schemas.py
│  │  ├─ storage/db.py
│  │  └─ services/
│  │     ├─ scorer.py
│  │     ├─ indexer.py
│  │     └─ reporter.py
│  └─ dashboard/app.py
├─ data/
│  ├─ raw/
│  ├─ interim/
│  └─ processed/
├─ notebooks/
├─ tests/test_sanity.py
└─ scripts/
   ├─ run_all.sh
   └─ cron_example.sh
```

---

## 里程碑建議
- W1~W2：ETL/清理/NER，完成 DB 與 API 骨架
- W3：Baseline 訓練與驗證（F1/PR/AUC）
- W4：聚合情緒指數、回測（IC/命中率/事件研究）
- W5：RAG + 報告生成（含引用）
- W6：Docker 化、Dashboard 打磨、Demo 劇本

---

## 注意事項
- 目前 LLM 報告生成使用 **模板 + RAG 佔位**（不含外部 API 凭證）。
- Transformer 微調檔（`train_transformer.py`）提供**範本**，請依環境與資料調整。
- 請遵守資料來源版權與 robots 規範。

