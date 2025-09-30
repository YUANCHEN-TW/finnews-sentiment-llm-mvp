
import argparse, json
from datetime import datetime
from sqlalchemy import create_engine, text, Column, Integer, Unicode, UnicodeText, DateTime, Table, MetaData
from sqlalchemy.orm import sessionmaker
from src.config import DB_URL
from src.label.weak_rules import load_lexicon, score_sentence_zh

def ensure_table(engine):
    meta = MetaData()
    table = Table("news_sent", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("news_id", Integer, index=True),
        Column("sent_id", Integer),
        Column("lang", Unicode(16)),
        Column("sentence", UnicodeText),
        Column("rule_label", Integer),
        Column("rule_score", Integer),
        Column("keywords_json", UnicodeText),
        Column("created_at", DateTime),
    )
    meta.create_all(engine)
    return table

def run(lexicon_path: str, limit: int = 5000, days: int = 120, force_rebuild: bool = False):
    engine = create_engine(DB_URL, future=True)
    ensure_table(engine)
    Session = sessionmaker(bind=engine, future=True)
    cfg = load_lexicon(lexicon_path)

    with Session() as s:
        q = text('''
            SELECT TOP (:limit) p.news_id, p.lang, p.sentences_json
            FROM news_proc p
            WHERE p.created_at >= DATEADD(day, -:days, GETUTCDATE())
            ORDER BY p.news_id DESC
        ''')
        rows = s.execute(q, {"limit": limit, "days": days}).all()

        if force_rebuild:
            s.execute(text("DELETE FROM news_sent"))
            s.commit()

        cnt = 0
        for news_id, lang, sjson in rows:
            try:
                sents = json.loads(sjson) if sjson else []
            except Exception:
                sents = []
            for i, sent in enumerate(sents):
                if not sent or (lang != "zh"):
                    continue
                label, info = score_sentence_zh(sent, cfg)
                s.execute(
                    text("""
                        INSERT INTO news_sent (news_id, sent_id, lang, sentence, rule_label, rule_score, keywords_json, created_at)
                        VALUES (:news_id, :sid, :lang, :sentence, :label, :score, :kw, :ts)
                    """),
                    {
                        "news_id": news_id,
                        "sid": i,
                        "lang": lang,
                        "sentence": sent,
                        "label": label,
                        "score": int(info["raw_score"]),
                        "kw": json.dumps({k: info[k] for k in ["pos_hits","neg_hits","negations","intensifiers","dampeners"]}, ensure_ascii=False),
                        "ts": datetime.utcnow()
                    }
                )
                cnt += 1
        s.commit()
    print(f"完成 news_sent 生成，共 {cnt} 句（中文）。")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lexicon", type=str, default="data/lexicon/zh_sentiment.yaml")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--force-rebuild", action="store_true")
    args = ap.parse_args()
    run(lexicon_path=args.lexicon, limit=args.limit, days=args.days, force_rebuild=args.force_rebuild)
