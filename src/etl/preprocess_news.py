import argparse, json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.config import DB_URL
from src.app.storage.models_ext import Base, NewsProc
from src.app.storage.models import News
from src.nlp.preprocess import preprocess_document

def run(limit: int = 1000, days: int = 90, dry_run: bool = False):
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as s:
        q = text('''
            SELECT TOP (:limit) n.id, n.title, n.content, n.published_at
            FROM news n
            WHERE n.published_at >= DATEADD(day, -:days, GETUTCDATE())
              AND NOT EXISTS (SELECT 1 FROM news_proc p WHERE p.news_id = n.id)
            ORDER BY n.published_at DESC
        ''')
        rows = s.execute(q, {"limit": limit, "days": days}).all()
        cnt = 0
        for rid, title, content, pub in rows:
            r = preprocess_document(title, content)
            rec = NewsProc(
                news_id=rid,
                lang=r.lang,
                cleaned=r.cleaned,
                sentences_json=json.dumps(r.sentences, ensure_ascii=False),
                created_at=datetime.utcnow()
            )
            if not dry_run:
                s.add(rec)
            cnt += 1
        if not dry_run:
            s.commit()
        print(f"完成前處理：{cnt} 筆（dry_run={dry_run})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(limit=args.limit, days=args.days, dry_run=args.dry_run)
