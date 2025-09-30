
# Step 2 — NLP 前處理

## 目的
對新聞標題與內文進行清洗、斷句、去除無效內容，為後續句級推論與標註做準備。

## 主要輸出表
- `news_sentence`：句子級切分結果（`news_id`, `sid`, `sentence`, `lang`, `cleaned`）

## 相關程式碼（重點）
- `src/nlp/preprocess.py`：清洗與正規化、斷詞/標點處理；
- `src/nlp/sent_tokenize.py`：中英文混合斷句（已修正 look-behind 固定長度問題）；
- `src/etl/preprocess_news.py`：將清洗後結果寫入 DB。

## 使用方式（指令）
```bash
# 以最近 N 天新聞為來源，寫入句級表
python -m src.etl.preprocess_news --days 7 --limit 20000 --dry-run 0
```

## 閃退防護
- 以 `--limit` 分批，並加入 `--dry-run` 模式先驗證；
- 迴圈內加入 `sleep/throttle-ms`，避免 CPU 飆高；
- 斷句 regex 已避用可變寬度 look-behind，確保相容。
