"""
用 HuggingFace Transformers 訓練中文句級情緒分類（BERT/Roberta）。
相容 transformers 新舊參數命名（evaluation_strategy / eval_strategy 等）。
且提供簡易 GPU 自動調參，避免 OOM/當機。

執行：
    python -m src.models.train_transformer --model_name hfl/chinese-bert-wwm-ext --epochs 1 --batch_size 4 --fp16
"""
import os, argparse, inspect
import numpy as np
import evaluate
from datasets import Dataset, DatasetDict
from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                          DataCollatorWithPadding, Trainer, TrainingArguments)
from src.models.datasets import default_paths, load_splits

def build_hf_dataset(dfs):
    ds = {}
    for split, df in dfs.items():
        ds[split] = Dataset.from_pandas(df.rename(columns={"sentence":"text"}), preserve_index=False)
    for split in ds:
        ds[split] = ds[split].map(lambda ex: {"label": int(ex["label"]) + 1})
    return DatasetDict(ds)

def compat_training_arguments(args, metric_name="f1_macro") -> TrainingArguments:
    sig = set(inspect.signature(TrainingArguments.__init__).parameters.keys())
    kwargs = {
        "output_dir": args.output_dir,
        "learning_rate": args.lr,
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.eval_batch_size or args.batch_size,
        "num_train_epochs": args.epochs,
        "logging_steps": 50,
        "report_to": "none",
        "seed": args.seed,
        "fp16": args.fp16,
    }
    if "evaluation_strategy" in sig:
        kwargs["evaluation_strategy"] = "epoch"
    elif "eval_strategy" in sig:
        kwargs["eval_strategy"] = "epoch"
    if "save_strategy" in sig:
        kwargs["save_strategy"] = "epoch"
    if "load_best_model_at_end" in sig:
        kwargs["load_best_model_at_end"] = True
    if "metric_for_best_model" in sig:
        kwargs["metric_for_best_model"] = metric_name
    filtered = {k: v for k, v in kwargs.items() if k in sig}
    return TrainingArguments(**filtered)

def auto_tune_args(args):
    try:
        import torch
        if torch.cuda.is_available():
            if args.mem_fraction and hasattr(torch.cuda, "set_per_process_memory_fraction"):
                try:
                    torch.cuda.set_per_process_memory_fraction(min(max(args.mem_fraction, 0.1), 0.95), 0)
                except Exception:
                    pass
            try:
                free, total = torch.cuda.mem_get_info(device=0)
            except Exception:
                free, total = (2*1024**3, 8*1024**3)
            if free < 2.0 * (1024**3):
                args.batch_size = max(2, min(args.batch_size, 4))
                args.max_length = min(args.max_length, 96)
            elif free < 4.0 * (1024**3):
                args.batch_size = max(4, min(args.batch_size, 8))
                args.max_length = min(args.max_length, 128)
    except Exception:
        pass
    return args

def main(cli):
    paths = default_paths(cli.dataset_root)
    dfs = load_splits(paths)
    dsd = build_hf_dataset(dfs)

    tokenizer = AutoTokenizer.from_pretrained(cli.model_name, use_fast=True)
    dsd = dsd.map(lambda b: tokenizer(b["text"], truncation=True, max_length=cli.max_length), batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(cli.model_name, num_labels=3)
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    metric_f1 = evaluate.load("f1")
    metric_acc = evaluate.load("accuracy")

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        return {
            "accuracy": metric_acc.compute(predictions=preds, references=labels)["accuracy"],
            "f1_macro": metric_f1.compute(predictions=preds, references=labels, average="macro")["f1"],
        }

    training_args = compat_training_arguments(cli, metric_name="f1_macro")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dsd["train"],
        eval_dataset=dsd["val"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    print("Test:", trainer.evaluate(dsd["test"]))

    trainer.save_model(cli.output_dir)
    tokenizer.save_pretrained(cli.output_dir)
    with open(os.path.join(cli.output_dir, "label_mapping.txt"), "w", encoding="utf-8") as f:
        f.write("id\tlabel\n0\tneg\n1\tneu\n2\tpos\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_name", type=str, default="hfl/chinese-bert-wwm-ext")
    ap.add_argument("--dataset_root", type=str, default="data/processed/dataset_v1")
    ap.add_argument("--output_dir", type=str, default="models/bert_sentence_cls")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--eval_batch_size", type=int, default=None)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max_length", type=int, default=128)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--mem_fraction", type=float, default=0.0, help="限制本進程可用 GPU 記憶體比例（0~1）")
    ap.add_argument("--auto_tune", action="store_true", help="自動根據顯存調整 batch_size / max_length（安全模式）")
    cli = ap.parse_args()
    if cli.auto_tune:
        cli = auto_tune_args(cli)
    main(cli)
