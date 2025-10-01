
# Step 4 — 句級分類模型訓練（Transformer 嚴格模式）

## 目的
以中文 BERT/FinBERT 變體做句級情緒分類，產出文級分數與句級分數。

1. **事件脈絡**（LDA 或 keyphrase） → 讓 LLM 報告掌握新聞的主題/事件
2. **連續情緒分數 + 實體關聯** → 句級/文級的連續分數（-1~1），並標註公司/產業

嚴格模式：API/儀表板不可 fallback，模型未載入則回 503。

## 相關程式碼（重點）
- `src/models/__init__.py`：讓 models 成為可 import 的套件
- `src/models/datasets.py`：載入 train/val/test CSV 並做基本欄位檢查
- `src/models/train_transformer.py`：使用 HF Trainer 訓練（BERT/Roberta 皆可）
- `src/models/infer_transformer.py`：推論腳本（單句或檔案）
- `src/app/model_registry.py`：嚴格的模型管理：只允許 Transformer，沒載到就 raise
- `src/app/main_strict.py`：FastAPI 嚴格版：/score 無模型直接 503，不做回退
- `src/app/load_model.py`：CLI 載入檢查（python -m src.app.load_model）
- `src/dashboard/app_strict.py`：Dashboard 嚴格版：未載入就只顯示「模型未載入」
- `src/dashboard/report_strict.py`：Streamlit 報告頁（模型未載入時只顯示「模型未載入」）
- `data/entities/companies.yaml`：公司/代碼/別名字典（可擴充）
- `src/nlp/topic_keyphrase.py`：事件脈絡：YAKE 關鍵詞 + 可選 LDA，寫入 news_event
- `src/models/sentence_score.py`：句級 Transformer 機率→連續分數，回填 news_sent
- `src/models/doc_aggregate.py`：將句級分數聚合為文級（新聞級），寫入 news_doc_sentiment
- `src/etl/entity_link.py`：字典式實體連結（公司/產業），寫入 news_entity

## 使用方式（指令）

### 1) 開始訓練（Transformer）
下面以 **Chinese BERT WWM** 為例；都用 **module 執行方式**：

```
python -m src.models.train_transformer --model_name hfl/chinese-bert-wwm-ext --epochs 1 --batch_size 4 --fp16 --auto_tune --mem_fraction 0.8
```

* 可改其他中文模型：

  * `bert-base-chinese`
  * `hfl/chinese-roberta-wwm-ext`
  * `uer/roberta-base-chinese-cluecorpussmall`
    
* 訓練成果與最佳模型會存在 `models/bert_sentence_cls/`
* 會列印 test 集的 `accuracy` 與 `f1_macro`
* --auto_tune：偵測可用顯存，如果 < 2GB / < 4GB，自動調低 batch_size 與 max_length
* --mem_fraction 0.8：限制本程序最多使用 80% 顯存（支援的 CUDA 版本才會生效）
* 將 `-1/0/1` 轉為 `0/1/2` 供模型訓練（已寫在 `label_mapping.txt`）。
* 若裝好 CUDA 版 PyTorch，可加 `--fp16`，速度更快。

* 防閃退要點：
    * 把 epoch 和 batch size 調小，可 --auto_tune 自動依顯存往下調。
    * --mem_fraction 限制本程式可用顯存比例（例如 0.8）。

---
單句推論：

```
python -m src.models.infer_transformer --model_dir models/bert_sentence_cls --text "台積電法說會釋出利多，訂單上修"
```

批次推論（每行一句）：

```
python -m src.models.infer_transformer --model_dir models/bert_sentence_cls --file samples.txt
```

輸出會包含 `pred` 與 `probs`（neg/neu/pos）。

---

### 2) 事件脈絡：關鍵詞 / LDA
寫入：`news_event(keyphrases_json, lda_topics_json)`

```bash
# YAKE + LDA（6 主題）
python -m src.nlp.topic_keyphrase --days 120 --limit 2000 --lda-topics 6 --lda-passes 3 --throttle-ms 10

# 只抽關鍵詞（跳過 LDA）
python -m src.nlp.topic_keyphrase --days 120 --limit 5000 --no-lda --throttle-ms 5
```

* --max-docs、--lda-topics、--lda-passes，以及 --throttle-ms 節流。
* 因為 LDA 在大語料上易吃 CPU/RAM，需要主題時再開 LDA，且降低 limit + passes，避免長時間滿載。
  
### 3) 句級連續情緒分數（-1 ~ 1）
將 Transformer 機率回填到 `news_sent`：

* `prob_neg / prob_neu / prob_pos`
* `cont_score = -1*P(neg) + 0*P(neu) + 1*P(pos)`

```bash
python -m src.models.sentence_score --model_dir models/bert_sentence_cls --days 120 --limit 20000 --auto_tune --device auto --batch_size 4 --max_length 128 --throttle-ms 50 --mem_fraction 0.8
```

防閃退要點：

* 預設 batch=4、max_length，可 --auto_tune 自動依顯存往下調。
* 支援 --device {auto,cuda,cpu}，任何 GPU 失敗自動回退 CPU，不中斷流程。
* --mem_fraction 限制本程式可用顯存比例（例如 0.8）。
* 用 torch.inference_mode() 降低負載；批與批之間可 --throttle-ms 50，避免功耗/溫度尖峰。
* 每一步都包 try/except，防止 GPU 錯誤帶崩。

### 4) 文級（新聞級）分數彙總
把句級平均成文級，寫入 `news_doc_sentiment`

```bash
python -m src.models.doc_aggregate --days 120
```

### 5) 實體關聯（公司/產業）
用字典 `data/entities/companies.yaml` 做匹配，寫入 `news_entity(matched_json)`

```bash
python -m src.etl.entity_link --days 120 --limit 5000 --gaz data/entities/companies.yaml
```
可以在 YAML 裡擴充更多公司與別名；之後要升級為 NER / Linking 也能替換這個模組。

### 6) 啟動 API
```
# 建議先設定模型輸出資料夾
set MODEL_DIR=models/bert_sentence_cls
# 啟動 API（嚴格模式預設 ON）
uvicorn src.app.main_strict:app --reload
```

* `/health` 會顯示 `transformer_loaded` 狀態
* `/score` 若未載入模型 → **HTTP 503**（"Transformer 模型未載入（STRICT 模式）"）

```
#開啟 Dashboard
python -m streamlit run src/dashboard/app_strict.py
```

* 若模型未載入，畫面只顯示「⚠️ 模型未載入」提示，不會有任何分數或回退結果

---
## 流程總覽

1. **模型訓練 / 微調** → `train_transformer`（可選）
2. **句級推論 + 連續分數** → `sentence_score`（必跑）
3. **文級聚合** → `doc_aggregate`
4. **事件脈絡**（關鍵詞/主題）→ `topic_keyphrase`
5. **實體連結** → `entity_link`
6. **/report API 報告升級版** → 嚴格模式檢查模型載入

## 是否需要再跑 `train_transformer`

* **如果你只是用現成模型（hfl/chinese-bert-wwm-ext）推論** → **不用重新訓練**。保留 `models/bert_sentence_cls` 跑推論就好。

* **如果你有新標註數據、想微調模型** → **需要重新訓練**

## 每次上新資料後要跑的步驟

```bash
python -m src.models.sentence_score --model_dir models/bert_sentence_cls --days 120 --limit 20000 --auto_tune --device auto --batch_size 4 --max_length 128 --throttle-ms 50 --mem_fraction 0.8
python -m src.models.doc_aggregate --days 120
python -m src.nlp.topic_keyphrase --days 120 --limit 2000 --lda-topics 6 --lda-passes 3 --throttle-ms 10
python -m src.etl.entity_link --days 120 --limit 5000 --gaz data/entities/companies.yaml
```

## 報告查看
```bash
uvicorn src.app.main_strict:app --reload
python -m streamlit run src/dashboard/report_strict.py
```
---
