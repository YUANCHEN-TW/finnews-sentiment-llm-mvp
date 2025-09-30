
import argparse, os
import pandas as pd
from sqlalchemy import create_engine, text
from src.config import DB_URL

MAP = {"pos": 1, "neg": -1, "neu": 0, "": None}

def run(csv_path: str, annotator: str = "you", make_split: bool = True):
    engine = create_engine(DB_URL, future=True)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    df["gold_label"] = df["gold_label"].astype(str).str.strip().str.lower().map(MAP)
    df = df.dropna(subset=["gold_label"])
    df["gold_label"] = df["gold_label"].astype(int)

    with engine.begin() as conn:
        conn.execute(text("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='sent_labels' AND type='U')
            CREATE TABLE sent_labels(
                id INT IDENTITY(1,1) PRIMARY KEY,
                sent_row_id INT,
                gold_label INT,
                annotator NVARCHAR(64),
                created_at DATETIME2 DEFAULT SYSUTCDATETIME()
            )
        """))
        for _, r in df.iterrows():
            conn.execute(text("""
                INSERT INTO sent_labels (sent_row_id, gold_label, annotator)
                VALUES (:rid, :y, :ann)
            """), {"rid": int(r["sent_row_id"]), "y": int(r["gold_label"]), "ann": annotator})

    print(f"已匯入 {len(df)} 筆人工標註。")

    if make_split:
        df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
        n = len(df)
        n_train = int(n * 0.7)
        n_val = int(n * 0.15)
        splits = {
            "train": df.iloc[:n_train],
            "val": df.iloc[n_train:n_train+n_val],
            "test": df.iloc[n_train+n_val:],
        }
        outdir = os.path.join(os.path.dirname(csv_path), "dataset_v1")
        os.makedirs(outdir, exist_ok=True)
        for k, d in splits.items():
            d.to_csv(os.path.join(outdir, f"{k}.csv"), index=False, encoding="utf-8-sig")
        print("已輸出資料集：", outdir)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--annotator", default="you")
    ap.add_argument("--no-split", action="store_true")
    args = ap.parse_args()
    run(csv_path=args.csv, annotator=args.annotator, make_split=(not args.no_split))
