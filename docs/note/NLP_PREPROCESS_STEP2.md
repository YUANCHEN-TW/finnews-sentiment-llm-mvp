# NLP 前處理（Step 2）— SQL Server 版本

## 安裝新增套件
將以下內容加入 `requirements.txt` 後安裝：
```
langdetect
opencc-python-reimplemented
```

## 執行
```bash
python src\etl\preprocess_news.py --limit 2000 --days 120
```

## 結果
- 新增表：`news_proc`（不動原始 `news` 結構）
- 欄位：`news_id`, `lang`, `cleaned`, `sentences_json`, `created_at`
- 可用 SSMS 查詢：
```sql
SELECT TOP 10 * FROM news_proc ORDER BY id DESC;
```
