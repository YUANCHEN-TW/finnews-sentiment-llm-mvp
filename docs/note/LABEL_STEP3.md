
# Step 3：標註策略（弱監督＋人工校正）

1) 生成句子資料集並套用弱監督：
```bash
python src/etl/build_sentence_dataset.py --lexicon data/lexicon/zh_sentiment.yaml --limit 5000 --days 120
```

2) 匯出一批樣本供人工標註：
```bash
python src/etl/export_for_annotation.py --size 300
```

3) 將人工標註匯回 DB，並輸出 train/val/test：
```bash
python src/etl/import_annotations.py --csv data/processed/annotation_batch_YYYYMMDD.csv --annotator "<your_name>"
```
