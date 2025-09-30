
import argparse, os
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from src.config import DB_URL

def run(size: int = 200, balance: bool = True, outdir: str = "data/processed"):
    engine = create_engine(DB_URL, future=True)
    if balance:
        parts = []
        for lbl in (-1, 0, 1):
            q = text("SELECT TOP (:k) id as sent_row_id, sentence, rule_label FROM news_sent WHERE rule_label = :lbl ORDER BY NEWID()")
            parts.append(pd.read_sql(q, engine, params={"k": size//3, "lbl": lbl}))
        df = pd.concat(parts, ignore_index=True)
    else:
        q = text("SELECT TOP (:k) id as sent_row_id, sentence, rule_label FROM news_sent ORDER BY NEWID()")
        df = pd.read_sql(q, engine, params={"k": size})

    df["gold_label"] = ""
    df["notes"] = ""
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d")
    path = os.path.join(outdir, f"annotation_batch_{ts}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print("已輸出：", path)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=200)
    ap.add_argument("--no-balance", action="store_true")
    ap.add_argument("--outdir", type=str, default="data/processed")
    args = ap.parse_args()
    run(size=args.size, balance=(not args.no_balance), outdir=args.outdir)
