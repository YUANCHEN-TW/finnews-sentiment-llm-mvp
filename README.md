# 金融新聞情緒分析 + LLM 報告生成 (MVP)

## 專案簡介
這是一個 **金融新聞情緒分析 + LLM 報告生成** 專案，
目標是建構一個從 **金融新聞** 自動化萃取、量化情緒，再透過 **回測** 與 **生成式 AI 報告**，協助投資研究與風險控管的系統。

最終成果包含：

* **ETL**：新聞/公告/社群資料自動抓取與儲存
* **NLP 模型**：基於 Transformer 的中文情緒分析
* **情緒指標建構**：市場/產業/個股層級的聚合 + 去噪 + 驚奇度
* **金融回測**：IC / RankIC、命中率、事件研究
* **LLM 報告生成**：檢索增強 (RAG) + Guardrails
* **產品化**：FastAPI REST API + Streamlit Dashboard

專案特色：
- **嚴格 Transformer 模式**：若模型未載入，API/Dashboard 會直接提示「模型未載入」，避免回退混淆。
- **防閃退機制**：所有重載/迴圈處都有防護（記憶體降載、自動回退、逾時控制）。
- **模組化**：各步驟都有獨立檔案與 CLI 指令。

---
## 系統架構

```
ETL → NLP (Transformer) → Signals → Backtest → API → Dashboard → LLM Report
```

---
## 步驟流程總覽

### Step 0. 測試環境
- Python 3
- Windows
- SQL Server (參照/docs/SQLServer_SETUP)
  
### Step 1. ETL（新聞擷取與儲存）
### Step 2. NLP 前處理
### Step 3. 標註策略（弱監督＋人工校正）
### Step 4. 模型訓練（Transformer）
### Step 5. 情緒指標建構（Signal Engineering）
### Step 6. 金融對齊與回測
### Step 7. LLM 報告生成（RAG + Guardrails）
### Step 8. API 與 Dashboard

以上請參照 docs 內的文件。

---
## 未來延伸

* 加入更多新聞來源（公告、社群）。
* 增強回測（多資產、跨市比較）。
* 自動化部署（Docker + GCP Cloud Run + Cloud Scheduler）。


## 注意事項

* **可能閃退風險**：模型訓練、回測、大量新聞擷取時，記憶體/CPU 負載高，程式已加入自動降載、防止 crash 的機制。

---

