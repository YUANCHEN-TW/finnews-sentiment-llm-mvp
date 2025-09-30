
# Step 1 — 資料擷取與落地（ETL/ELT）

## 目的
從新聞來源取得原始資料，落地至 SQL Server，形成可追溯、可重跑的原始表。

## 主要資料表（建議）
- `news`（或 `news_raw`）：原始新聞（`id/news_id`, `title`, `content`, `source`, `url`, `published_at`）
- `news_ingest_log`：擷取批次紀錄（來源、期間、筆數、耗時、狀態）

## 相關程式碼（重點）
- `src/etl/fetch_news.py`：抓取來源 API/爬蟲，寫入 `news`
- `src/etl/dedup.py`：以（title+source+published_at）或內容相似度去重
- `src/config.py`：`DB_URL` 設定（SQL Server／ODBC 連線字串）

## 使用方式（指令）
```bash
# 擷取原始新聞（範例）
python -m src.etl.fetch_news --days 3 --limit 5000

# 去重（可選）
python -m src.etl.dedup --days 7
```

## 閃退防護
- 來源分批抓取（`--limit`），網路請求加超時與重試；
- DB 端採小連線池（pool_size=3, max_overflow=2）；
- 以日期分段重跑，避免一次處理過多資料造成記憶體飆升。
