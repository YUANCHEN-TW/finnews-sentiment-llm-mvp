# Transformers TrainingArguments 相容層 + 安全自動調參

- 動態檢查 `TrainingArguments.__init__` 可用參數：存在 `evaluation_strategy` 就用它；否則用 `eval_strategy`。
- 其他相容：`save_strategy`、`load_best_model_at_end`、`metric_for_best_model`。
- 避免 OOM/當機：加上 `--auto_tune`（自動降 batch_size/max_length）；或 `--mem_fraction 0.7` 限制本程序最多占用 70% 顯存。

範例：
```
python -m src.models.train_transformer --model_name hfl/chinese-bert-wwm-ext --epochs 1 --batch_size 4 --fp16 --auto_tune --mem_fraction 0.8
```
