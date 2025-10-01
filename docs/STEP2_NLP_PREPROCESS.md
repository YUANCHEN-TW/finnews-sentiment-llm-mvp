
# Step 2 — NLP 前處理

## 目的
對新聞標題與內文進行清洗、斷句、去除無效內容，為後續句級推論與標註做準備。

## 主要輸出表
- `news_sentence`：句子級切分結果（`news_id`, `sid`, `sentence`, `lang`, `cleaned`）

## 相關程式碼（重點）
- `src/app/storage/models_ext.py`：新表 news_proc 的 SQLAlchemy 定義
- `src/nlp/sent_tokenize.py`：中英文混合斷句（已修正 look-behind 固定長度問題）
- `src/nlp/preprocess.py`：清理→語言偵測→（中）繁體化→句切流程
- `src/etl/preprocess_news.py`：從 news 讀→寫入 news_proc 的執行腳本
- 
## 使用方式（指令）
```bash
# 以最近 N 天新聞為來源，寫入句級表
python -m src.etl.preprocess_news --days 120 --limit 20000 --dry-run 0
```

* dry_run=True：只會跑流程（讀取新聞 → 前處理 → 計算句子等），不會真的寫回資料庫。
* limit：最多要處理幾筆新聞，超過 limit 的新聞就不會被選出來，也就不會進入後面的前處理流程。
* 會把最近 120 天、尚未處理過的新聞做：清理→語言偵測→（中文）簡轉繁→句子切分
* 寫到新表 `news_proc`（不動原始 `news` 結構）

檢查成果（SSMS）：

```sql
SELECT TOP 10 * FROM news_proc ORDER BY id DESC;
```

你會看到：

* `lang`：`zh` 或 `en` 等
* `cleaned`：清理後的全文（標題＋內文）
* `sentences_json`：句子陣列（JSON 字串）

---

## 常見卡點

* `ImportError: No module named opencc` → 重新安裝 `opencc-python-reimplemented`；這個版本是純 Python，Windows OK。
* `news_proc` 沒建立 → 確認 `preprocess_news.py` 開頭有 `Base.metadata.create_all(engine)`，或你有讀取 `.env` 指到 SQL Server。
* 預設只處理最近 N 天且尚未處理過的新聞；要重跑可先清掉 `news_proc` 對應 `news_id` 的資料，或改 `--days`/`--limit`。
