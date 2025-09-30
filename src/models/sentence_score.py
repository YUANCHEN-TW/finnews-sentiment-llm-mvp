"""穩定版：句級連續情緒打分（避免閃退）。
- 小 batch 預設、裝置自動選擇與 CPU 回退、顯存比例限制、批次節流。
用法：
  python -m src.models.sentence_score --model_dir models/bert_sentence_cls --days 120 --limit 20000 --auto_tune --throttle-ms 50
"""
import argparse, time
from sqlalchemy import create_engine, text
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from src.config import DB_URL

def ensure_columns(engine):
    with engine.begin() as conn:
        for col in ["prob_neg","prob_neu","prob_pos","cont_score"]:
            conn.execute(text(f"""
                IF COL_LENGTH('news_sent', '{col}') IS NULL
                    ALTER TABLE news_sent ADD {col} FLOAT NULL
            """))

def _auto_tune(args):
    try:
        if args.device in ("auto", "cuda") and torch.cuda.is_available():
            if args.mem_fraction and hasattr(torch.cuda, "set_per_process_memory_fraction"):
                try:
                    torch.cuda.set_per_process_memory_fraction(min(max(args.mem_fraction, 0.1), 0.95), 0)
                except Exception:
                    pass
            try:
                free, _ = torch.cuda.mem_get_info(0)
            except Exception:
                free = 2 * 1024**3
            if free < 2 * 1024**3:
                args.batch_size = min(args.batch_size, 2)
                args.max_length = min(args.max_length, 96)
            elif free < 4 * 1024**3:
                args.batch_size = min(args.batch_size, 4)
                args.max_length = min(args.max_length, 128)
    except Exception:
        pass
    return args

def _pick_device(args):
    if args.device == "cpu":
        return torch.device("cpu")
    if args.device == "cuda":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

def run(model_dir: str, days:int, limit:int, max_length:int=128, batch_size:int=4,
        device:str="auto", mem_fraction:float=0.0, auto_tune:bool=False, throttle_ms:int=0):
    engine = create_engine(DB_URL, future=True)
    ensure_columns(engine)

    tok = AutoTokenizer.from_pretrained(model_dir)
    mdl = AutoModelForSequenceClassification.from_pretrained(model_dir)

    class _A: pass
    a = _A(); a.device=device; a.mem_fraction=mem_fraction; a.batch_size=batch_size; a.max_length=max_length
    if auto_tune:
        a = _auto_tune(a)
    dev = _pick_device(a)
    try:
        mdl.to(dev)
    except Exception:
        dev = torch.device("cpu"); mdl.to(dev)

    with engine.begin() as conn:
        rows = conn.execute(text('''
            SELECT TOP (:limit) id, sentence
            FROM news_sent
            WHERE created_at >= DATEADD(day, -:days, GETUTCDATE())
              AND cont_score IS NULL
            ORDER BY id DESC
        '''), {"limit": limit, "days": days}).fetchall()

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    count = 0
    for batch in chunks(rows, a.batch_size):
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]
        try:
            inputs = tok(texts, return_tensors="pt", truncation=True, padding=True, max_length=a.max_length)
            inputs = {k: v.to(dev) for k, v in inputs.items()}
            with torch.inference_mode():
                out = mdl(**inputs)
                probs = torch.softmax(out.logits, dim=-1).cpu().tolist()
        except Exception:
            dev = torch.device("cpu"); mdl.to(dev)
            inputs = tok(texts, return_tensors="pt", truncation=True, padding=True, max_length=a.max_length)
            with torch.inference_mode():
                out = mdl(**inputs)
                probs = torch.softmax(out.logits, dim=-1).tolist()

        scores = [(-1)*p[0] + 0*p[1] + 1*p[2] for p in probs]
        with engine.begin() as conn:
            for rid, p, s in zip(ids, probs, scores):
                conn.execute(text("""
                    UPDATE news_sent SET prob_neg=:a, prob_neu=:b, prob_pos=:c, cont_score=:s
                    WHERE id=:rid
                """), {"a": float(p[0]), "b": float(p[1]), "c": float(p[2]), "s": float(s), "rid": int(rid)})
                count += 1
        if throttle_ms > 0:
            time.sleep(throttle_ms/1000.0)
    print(f"已更新句級連續分數：{count} 句")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_dir", type=str, default="models/bert_sentence_cls")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--max_length", type=int, default=128)
    ap.add_argument("--batch_size", type=int, default=4)
    ap.add_argument("--device", choices=["auto","cuda","cpu"], default="auto")
    ap.add_argument("--mem_fraction", type=float, default=0.0)
    ap.add_argument("--auto_tune", action="store_true")
    ap.add_argument("--throttle-ms", type=int, default=0)
    args = ap.parse_args()
    run(model_dir=args.model_dir, days=args.days, limit=args.limit, max_length=args.max_length,
        batch_size=args.batch_size, device=args.device, mem_fraction=args.mem_fraction,
        auto_tune=args.auto_tune, throttle_ms=args.throttle_ms)
