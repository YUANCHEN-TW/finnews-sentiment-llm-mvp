"""文級（新聞級）分數彙總（批次 + 節流）。"""
import argparse, time
from sqlalchemy import create_engine, text
from src.config import DB_URL

def ensure_table(engine):
    from sqlalchemy import Table, MetaData, Column, Integer, Float, DateTime
    meta = MetaData()
    Table('news_doc_sentiment', meta,
          Column('id', Integer, primary_key=True, autoincrement=True),
          Column('news_id', Integer, index=True, unique=True),
          Column('doc_prob_neg', Float),
          Column('doc_prob_neu', Float),
          Column('doc_prob_pos', Float),
          Column('doc_score', Float),
          Column('n_sents', Integer),
          Column('created_at', DateTime))
    meta.create_all(engine)

def run(days:int, throttle_ms:int=0):
    engine = create_engine(DB_URL, future=True)
    ensure_table(engine)
    with engine.begin() as conn:
        rows = conn.execute(text('''
            SELECT s.news_id,
                   AVG(s.prob_neg) as pneg,
                   AVG(s.prob_neu) as pneu,
                   AVG(s.prob_pos) as ppos,
                   AVG(s.cont_score) as score,
                   COUNT(*) as n
            FROM news_sent s
            WHERE s.cont_score IS NOT NULL
              AND s.created_at >= DATEADD(day, -:days, GETUTCDATE())
            GROUP BY s.news_id
        '''), {"days": days}).fetchall()
    engine.dispose()
    engine = create_engine(DB_URL, future=True)
    for i, (nid, pneg, pneu, ppos, score, n) in enumerate(rows):
        with engine.begin() as conn:
            conn.execute(text("""
                MERGE news_doc_sentiment AS t
                USING (SELECT :nid AS news_id) AS src
                ON (t.news_id = src.news_id)
                WHEN MATCHED THEN UPDATE SET
                    doc_prob_neg=:a, doc_prob_neu=:b, doc_prob_pos=:c, doc_score=:s,
                    n_sents=:n, created_at=SYSUTCDATETIME()
                WHEN NOT MATCHED THEN INSERT (news_id, doc_prob_neg, doc_prob_neu, doc_prob_pos, doc_score, n_sents, created_at)
                VALUES (:nid, :a, :b, :c, :s, :n, SYSUTCDATETIME());
            """), {"nid": int(nid), "a": float(pneg or 0), "b": float(pneu or 0), "c": float(ppos or 0),
                     "s": float(score or 0), "n": int(n or 0)})
        if throttle_ms > 0:
            time.sleep(throttle_ms/1000.0)
    print(f"已更新文級情緒 {len(rows)} 篇")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--throttle-ms", type=int, default=0)
    args = ap.parse_args()
    run(days=args.days, throttle_ms=args.throttle_ms)
