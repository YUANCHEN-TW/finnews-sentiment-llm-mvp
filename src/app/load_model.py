"""Helper：以模組方式手動載入模型，便於在部署前檢查可用性。
用法：
    python -m src.app.load_model --model_dir models/bert_sentence_cls
"""
import argparse
from src.app.model_registry import load_transformer

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_dir", type=str, default=None)
    args = ap.parse_args()
    path = load_transformer(args.model_dir)
    print("模型已載入：", path)

if __name__ == "__main__":
    main()
