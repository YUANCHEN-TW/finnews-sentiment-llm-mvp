
# Step 1 — 資料擷取與落地（ETL/ELT）

## 目的
從新聞來源取得原始資料，落地至 SQL Server，形成可追溯、可重跑的原始表。

## 主要資料表（建議）
- `news`（或 `news_raw`）：原始新聞（`id/news_id`, `title`, `content`, `source`, `url`, `published_at`）
- `news_ingest_log`：擷取批次紀錄（來源、期間、筆數、耗時、狀態）

## 相關程式碼（重點）
- `src/app/storage/models.py`： 把資料表結構集中並使用 Unicode 欄位（適配 MSSQL）
- `src/etl/demo_seed.py`： 改為使用上面的 models.py（MSSQL 也可 seed）
- `src/etl/rss_to_db.py`： 從 RSS 抓新聞→寫入 SQL Server 的指令稿（可多個 --url），寫入 `news`
  
## 使用方式（指令）
```bash
# 擷取原始新聞（範例）
python -m src.etl.rss_to_db --url "https://<你的RSS1>" --url "https://<你的RSS2>"

#注意：`rss_to_db.py` 會依 `url` 欄位做**唯一鍵**避免重複塞入。若遇到部分來源格式怪，先用一個能正常回傳 RSS 的來源測試（你之後可自由擴充）。
```

## 常見錯誤排除
* **`pyodbc.Error: ('01000', ...) Driver not found`**
  → 尚未安裝 ODBC Driver 18；請安裝後重開命令列。

* **`Login failed for user`**
  → 帳密錯誤或 SQL Server 沒有啟用混合驗證；請在 SSMS 啟用或改用 Windows 驗證建立對應使用者。

* **`('HYT00', 'Login timeout expired')`**
  → 連不到主機/埠（1433）。檢查防火牆與 SQL Server Browser。

* **`('28000', '[Microsoft][ODBC Driver 18 for SQL Server]SSL Provider: ...')`**
  → 先在連線字串保留 `TrustServerCertificate=yes`，或設定正確的憑證。
