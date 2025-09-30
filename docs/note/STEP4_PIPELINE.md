
# Step 4 全流程指引（Transformer 嚴格模式）

> 目的：用 **已訓練好的 Transformer** 進行句級推論，產出**連續情緒分數**，彙總成**文級分數**，
> 再補上**事件脈絡（關鍵詞/主題）**與**實體關聯（公司/產業）**，最後用嚴格 `/report` 出報表。

---

## 0) 何時需要重新訓練？（train_transformer）
- **不需重訓**：只是上新資料做分析/報告，沿用既有模型即可。
- **需要重訓**（擇一成立就重訓）：
  - 新增了人工標註資料（`data/processed/dataset_v1/*` 更新）。
  - 想換更好的預訓練底座（e.g., `hfl/chinese-bert-wwm-ext` → `hfl/chinese-roberta-wwm-ext`）。

重訓安全範例：
```bash
python -m src.models.train_transformer   --model_name hfl/chinese-bert-wwm-ext   --epochs 1   --batch_size 4   --fp16   --auto_tune   --mem_fraction 0.8
```
> 若 GPU 不穩，拿掉 `--fp16` 或改用 CPU 訓練（視環境而定）。

---

## 1) 句級推論 → 連續分數（必跑）
將 Transformer 機率寫回 `news_sent`：`prob_neg/prob_neu/prob_pos/cont_score`，`cont_score ∈ [-1,1]`。
```bash
python -m src.models.sentence_score   --model_dir models/bert_sentence_cls   --days 120 --limit 20000   --auto_tune --throttle-ms 50
```
**安全參數說明：**
- `--auto_tune`：自動依顯存調小 batch/長度。
- `--throttle-ms 50`：批與批之間暫停 50ms，降低功耗/溫度尖峰。
- `--device cpu`：若機器常閃退，直接改 CPU 最安全（較慢）。
- `--mem_fraction 0.8`：限制本程序最多使用 80% 顯存（某些環境才有效）。

---

## 2) 文級聚合（必跑）
把句級平均成文級，寫入/更新 `news_doc_sentiment`：
```bash
python -m src.models.doc_aggregate --days 120
```

---

## 3) 事件脈絡（關鍵詞 / 主題）
寫入 `news_event(keyphrases_json, lda_topics_json)`：
```bash
# 建議預設只跑關鍵詞（YAKE）：
python -m src.nlp.topic_keyphrase --days 120 --limit 5000 --no-lda --throttle-ms 5

# 需要主題（LDA）時，先小量測試：
python -m src.nlp.topic_keyphrase --days 120 --limit 2000 --lda-topics 6 --lda-passes 3 --throttle-ms 10
```

---

## 4) 實體關聯（公司/產業）
用字典 `data/entities/companies.yaml` 做字串匹配，寫入 `news_entity(matched_json)`：
```bash
python -m src.etl.entity_link --days 120 --limit 5000 --batch-size 200 --throttle-ms 10
```

---

## 5) 嚴格模式報告（/report）
啟動 API（嚴格：未載入模型 → 503）：
```bash
# Windows PowerShell
set MODEL_DIR=models/bert_sentence_cls
uvicorn src.app.main_strict:app --reload
```
```bash
# Linux / macOS
export MODEL_DIR=models/bert_sentence_cls
uvicorn src.app.main_strict:app --reload
```

查看報告：
```bash
# 多篇（依 news_id DESC）
GET /report?limit=50&days=120

# 指定單篇
GET /report?news_id=12345
```

Streamlit 報告頁（嚴格版）：
```bash
streamlit run src/dashboard/report_strict.py
```

---

## 常見問題（FAQ）
- **跑推論會閃退？**  
  用 `--device cpu`，或加上 `--auto_tune --throttle-ms 50 --mem_fraction 0.8`。硬體問題（電源/散熱）也要留意。
- **/report 說模型未載入？**  
  確認 `MODEL_DIR` 指到可用的訓練輸出資料夾，或先執行：  
  ```bash
  python -m src.app.load_model --model_dir models/bert_sentence_cls
  ```
- **報告想看到標題/連結？**  
  可在 API 裡 join 你 `news_raw` 或 `news_proc` 的 `title/url` 欄位（我能替你加）。
