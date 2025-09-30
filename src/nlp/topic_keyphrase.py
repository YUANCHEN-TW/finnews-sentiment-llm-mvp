"""事件脈絡：YAKE 關鍵詞 +（可選）LDA。資源友善。
預設不跑 LDA，並限制最大文件數與節流。
"""
import argparse, json, time
from datetime import datetime
from sqlalchemy import create_engine, text
from src.config import DB_URL
import jieba

def fetch_docs(days:int, limit:int, max_docs:int):
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        rows = conn.execute(text('''
            SELECT TOP (:limit) news_id, cleaned
            FROM news_proc
            WHERE created_at >= DATEADD(day, -:days, GETUTCDATE())
            ORDER BY news_id DESC
        '''), {"limit": min(limit, max_docs), "days": days}).all()
    return rows

def ensure_table(engine):
    from sqlalchemy import Table, MetaData, Column, Integer, UnicodeText, DateTime
    meta = MetaData()
    Table('news_event', meta,
          Column('id', Integer, primary_key=True, autoincrement=True),
          Column('news_id', Integer, index=True),
          Column('keyphrases_json', UnicodeText),
          Column('lda_topics_json', UnicodeText),
          Column('created_at', DateTime))
    meta.create_all(engine)

def run(days:int, limit:int, do_lda:bool, topk:int, max_docs:int, lda_topics:int, lda_passes:int, throttle_ms:int):
    rows = fetch_docs(days, limit, max_docs)
    engine = create_engine(DB_URL, future=True)
    ensure_table(engine)

    import yake
    kw_extractor = yake.KeywordExtractor(lan="zh", n=1, top=topk)

    lda_model = None
    doc_topics = None
    if do_lda and rows:
        from gensim import corpora, models
        docs_tokens = [[t for t in jieba.lcut(cleaned or "") if t.strip()] for _, cleaned in rows]
        dictionary = corpora.Dictionary(docs_tokens)
        corpus = [dictionary.doc2bow(toks) for toks in docs_tokens]
        lda_model = models.LdaModel(corpus=corpus, id2word=dictionary, num_topics=lda_topics, passes=lda_passes)
        doc_topics = [lda_model.get_document_topics(bow) for bow in corpus]

    with engine.begin() as conn:
        for idx, (news_id, cleaned) in enumerate(rows):
            kphr = kw_extractor.extract_keywords(cleaned or "")
            kphr = [k for k,score in kphr]
            lda = None
            if lda_model:
                topics = sorted(doc_topics[idx], key=lambda x: -x[1])[:3]
                lda = [{"topic": int(t), "prob": float(p)} for t,p in topics]
            conn.execute(text("""
                INSERT INTO news_event (news_id, keyphrases_json, lda_topics_json, created_at)
                VALUES (:nid, :k, :lda, :ts)
            """), {"nid": int(news_id),
                     "k": json.dumps(kphr, ensure_ascii=False),
                     "lda": json.dumps(lda, ensure_ascii=False) if lda is not None else None,
                     "ts": datetime.utcnow()})
            if throttle_ms > 0:
                time.sleep(throttle_ms/1000.0)
    print(f"完成：{len(rows)} 篇（keyphrase{'+LDA' if do_lda else ''}）寫入 news_event")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--no-lda", action="store_true")
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--max-docs", type=int, default=2000)
    ap.add_argument("--lda-topics", type=int, default=6)
    ap.add_argument("--lda-passes", type=int, default=3)
    ap.add_argument("--throttle-ms", type=int, default=0)
    args = ap.parse_args()
    run(days=args.days, limit=args.limit, do_lda=(not args.no_lda), topk=args.topk,
        max_docs=args.max_docs, lda_topics=args.lda_topics, lda_passes=args.lda_passes, throttle_ms=args.throttle_ms)
