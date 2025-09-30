"""推論：
python -m src.models.infer_transformer --model_dir models/bert_sentence_cls --text "台積電上修資本支出"
"""
import argparse, json
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

ID2LABEL = {0:"neg", 1:"neu", 2:"pos"}

def predict_one(model, tokenizer, text: str, max_length=128):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
    with torch.no_grad():
        out = model(**inputs)
        probs = torch.softmax(out.logits, dim=-1).squeeze(0).tolist()
        pred = int(torch.argmax(out.logits, dim=-1).item())
    return {"text": text, "pred": ID2LABEL[pred], "probs": {"neg": probs[0], "neu": probs[1], "pos": probs[2]}}

def main(args):
    tok = AutoTokenizer.from_pretrained(args.model_dir)
    mdl = AutoModelForSequenceClassification.from_pretrained(args.model_dir)
    if args.text:
        print(json.dumps(predict_one(mdl, tok, args.text, args.max_length), ensure_ascii=False))
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if line:
                    print(json.dumps(predict_one(mdl, tok, line, args.max_length), ensure_ascii=False))
    else:
        print("請用 --text 或 --file 指定輸入")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_dir", type=str, default="models/bert_sentence_cls")
    ap.add_argument("--text", type=str, default=None)
    ap.add_argument("--file", type=str, default=None)
    ap.add_argument("--max_length", type=int, default=128)
    args = ap.parse_args()
    main(args)
