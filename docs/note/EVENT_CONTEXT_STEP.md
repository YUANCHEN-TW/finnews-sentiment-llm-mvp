# 事件脈絡 + 連續情緒 + 實體關聯（Step 4 後半）

## 1) 關鍵詞/主題（事件脈絡）
寫入表：`news_event(keyphrases_json, lda_topics_json)`
```
python -m src.nlp.topic_keyphrase --days 120 --limit 5000
# 只跑關鍵詞：
python -m src.nlp.topic_keyphrase --days 120 --limit 5000 --no-lda
```

## 2) 句級連續情緒分數（Transformer）
回填 `news_sent`：`prob_neg/prob_neu/prob_pos/cont_score`
```
python -m src.models.sentence_score --model_dir models/bert_sentence_cls --days 120 --limit 20000
```

## 3) 文級（新聞級）分數彙總
寫入/更新 `news_doc_sentiment`
```
python -m src.models.doc_aggregate --days 120
```

## 4) 實體關聯（公司/產業）
使用字典 `data/entities/companies.yaml` 做字串比對
```
python -m src.etl.entity_link --days 120 --limit 5000 --gaz data/entities/companies.yaml
```
