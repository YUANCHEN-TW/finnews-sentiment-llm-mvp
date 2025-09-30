# 安全執行指南（避免閃退）

## B. 句級連續情緒（最容易負載高）
建議：
```
python -m src.models.sentence_score --model_dir models/bert_sentence_cls \\
  --days 120 --limit 20000 --auto_tune --device auto --batch_size 4 --max_length 128 --throttle-ms 50 --mem_fraction 0.8
```

## A. 事件脈絡（預設不跑 LDA）
```
python -m src.nlp.topic_keyphrase --days 120 --limit 5000 --no-lda --throttle-ms 5
# 真要 LDA：
python -m src.nlp.topic_keyphrase --days 120 --limit 2000 --lda-topics 6 --lda-passes 3 --throttle-ms 10
```

## C. 文級彙總（輕量）
```
python -m src.models.doc_aggregate --days 120 --throttle-ms 0
```

## D. 實體連結（CPU）
```
python -m src.etl.entity_link --days 120 --limit 5000 --batch-size 200 --throttle-ms 10
```
