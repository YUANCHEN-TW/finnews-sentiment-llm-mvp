
# Step 3 — 標註策略（弱監督 + 人工校正）

## 目的
以規則/辭典產生「弱標註」，再抽樣做人工作業校正，建立高品質訓練集。

## 為何需要人工批次？
- 弱標註在諷刺、雙關、金融脈絡（如「利空出盡」）上易誤判；
- 少量高品質標註可顯著提升模型泛化表現與可解釋性。

## 相關程式碼（重點）
- `data/lexicon/zh_sentiment.yaml`：中文情緒詞典（可自行擴充）
- `src/label/weak_rules.py`：弱監督規則打分（分詞→關鍵詞→否定/強化/減弱加權）
- `src/etl/build_sentence_dataset.py`：從 news_proc 生成句級資料集 news_sent（含 rule_label/score）
- `src/etl/export_for_annotation.py`：匯出平衡取樣的 CSV 給你人工標註
- `src/etl/import_annotations.py `：匯入人工標註到 DB，並輸出 train/val/test
- 
## 使用方式（指令）

### 1) 句子資料集（弱監督打分）

先確保你已完成 Step 2，有 `news_proc` 資料。然後執行：

```
python -m src.etl.build_sentence_dataset --lexicon data/lexicon/zh_sentiment.yaml --limit 5000 --days 120
```

這會建立/寫入表 `news_sent`，欄位包含：

* `sentence`：句子文字
* `rule_label`：弱監督標籤（-1 / 0 / 1）
* `rule_score`：加權分數（-3 … 3）
* `keywords_json`：命中的關鍵詞

### 2) 匯出人工標註批次（CSV）

```
python -m src.etl.export_for_annotation --size 300
```

* 會輸出到 `data/processed/annotation_batch_YYYYMMDD.csv`
* 打開 CSV，依照 `docs/ANNOTATION_GUIDE.md` 在 `gold_label` 欄填 `pos / neg / neu`

### 3) 匯入人工標註，輸出資料集切分

```
python -m src.etl.import_annotations --csv data/processed/annotation_batch_YYYYMMDD.csv --annotator "<你的名字>"
```

* 寫入表 `sent_labels`（保存你的人工標註）
* 同時在 `data/processed/dataset_v1/` 產出 `train.csv`, `val.csv`, `test.csv`

---

## 小貼士

* 想重建 `news_sent`：加 `--force-rebuild` 參數。
* 詞典可隨時擴充：編輯 `data/lexicon/zh_sentiment.yaml` 後重跑 `build_sentence_dataset.py`。
* 英文新聞：此版規則只處理中文；若你需要英文，我可以再給你 `en_sentiment.yaml` 與英文 scoring。
