
# Step 4 — 句級分類模型訓練（Transformer 嚴格模式）

## 目的
以中文 BERT/FinBERT 變體做句級情緒分類，產出文級分數與句級分數。

## 相關程式碼（重點）
- `src/models/train_transformer.py`：HuggingFace Trainer 訓練
  - 自動相容 `transformers` 新舊參數（`eval_strategy` / `evaluation_strategy`、`save_strategy` 等）
  - 安全參數：`--fp16`、`--auto_tune`、`--mem_fraction` 避免 OOM；
- `src/models/runtime.py`：推論載入與 `score_text()`；
- 嚴格模式：API/儀表板不可 fallback，模型未載入則回 503。

## 使用方式（指令）
```bash
# 訓練（範例）
python -m src.models.train_transformer --model_name hfl/chinese-bert-wwm-ext   --epochs 3 --batch_size 8 --fp16 --auto_tune --mem_fraction 0.8

# 推論（API 嚴格模式以此為準）
# 設定環境變數代表已載入
setx TRANSFORMER_READY 1
```

## 閃退防護
- 動態偵測 `transformers` 參數名；
- 控制 batch/grad_accum、啟用 fp16；
- 設置 VRAM/記憶體使用比例（`--mem_fraction`）。
