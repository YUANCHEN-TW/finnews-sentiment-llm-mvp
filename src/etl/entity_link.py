"""字典式實體連結（批次 + 節流）。"""
import argparse, yaml, json, re, time
from sqlalchemy import create_engine, text
from src.config import DB_URL

def load_gaz(path):
    with open(path, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    ents = []
    for c in y.get("companies", []):
        names = [c.get("name")] + c.get("aliases", [])
        ents.append({
            "ticker": c.get("ticker"),
            "name": c.get("name"),
            "industry": c.get("industry"),
            "aliases": [n for n in names if n],
        })
    for e in ents:
        pats = [re.escape(a) for a in e["aliases"] + [e["name"]]]
        e["regex"] = re.compile("|".join(sorted(set(pats), key=len, reverse=True)))
    return ents

def ensure_table(engine):
    from sqlalchemy import Table, MetaData, Column, Integer, UnicodeText, DateTime
    meta = MetaData()
    Table('news_entity', meta,
          Column('id', Integer, primary_key=True, autoincrement=True),
          Column('news_id', Integer, index=True),
          Column('matched_json', UnicodeText),
          Column('created_at', DateTime))
    meta.create_all(engine)

def run(days:int, limit:int, gaz_path:str, batch_size:int, throttle_ms:int):
    engine = create_engine(DB_URL, future=True)
    ensure_table(engine)
    ents = load_gaz(gaz_path)

    with engine.begin() as conn:
        rows = conn.execute(text('''
            SELECT TOP (:limit) p.news_id, p.cleaned
            FROM news_proc p
            WHERE p.created_at >= DATEADD(day, -:days, GETUTCDATE())
            ORDER BY p.news_id DESC
        '''), {"limit": limit, "days": days}).fetchall()

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    total = 0
    for batch in chunks(rows, batch_size):
        with engine.begin() as conn:
            for nid, cleaned in batch:
                hits = []
                for e in ents:
                    m = e["regex"].findall(cleaned or "")
                    if m:
                        hits.append({
                            "ticker": e["ticker"], "name": e["name"], "industry": e["industry"],
                            "matches": list(m), "count": len(m)
                        })
                if hits:
                    conn.execute(text("""
                        INSERT INTO news_entity (news_id, matched_json, created_at)
                        VALUES (:nid, :m, SYSUTCDATETIME())
                    """), {"nid": int(nid), "m": json.dumps(hits, ensure_ascii=False)})
                    total += 1
        if throttle_ms > 0:
            time.sleep(throttle_ms/1000.0)
    print(f"已建立實體連結：{total} 篇")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--gaz", type=str, default="data/entities/companies.yaml")
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--throttle-ms", type=int, default=0)
    args = ap.parse_args()
    run(days=args.days, limit=args.limit, gaz_path=args.gaz, batch_size=args.batch_size, throttle_ms=args.throttle_ms)
