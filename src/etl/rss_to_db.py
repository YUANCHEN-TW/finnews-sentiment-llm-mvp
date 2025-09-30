import asyncio
import argparse
from dateutil import parser as dtparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import DB_URL
from src.etl.clean import basic_clean
from src.etl.fetchers.rss_fetcher import fetch_rss
from src.app.storage.models import Base, News

async def main(urls):
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    tasks = [fetch_rss(u) for u in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total = 0
    with Session() as s:
        for url, res in zip(urls, results):
            if isinstance(res, Exception):
                print(f"[WARN] {url} 抓取失敗：{res}")
                continue
            for item in res:
                title = basic_clean(item.get("title", ""))
                content = basic_clean(item.get("description", ""))
                source = url
                link = item.get("link") or ""
                pub_raw = item.get("pubDate") or ""
                try:
                    published_at = dtparser.parse(pub_raw) if pub_raw else None
                except Exception:
                    published_at = None
                if not link:
                    continue
                n = News(title=title, content=content, source=source, url=link, published_at=published_at)
                try:
                    s.add(n)
                    s.flush()  # 觸發唯一鍵檢查（依賴 uq_news_url）
                    total += 1
                except Exception:
                    s.rollback()
                    s.begin()
                    continue
        s.commit()
    print(f"完成抓取，共新增 {total} 筆。")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="append", required=True, help="RSS feed URL，可重複指定")
    args = ap.parse_args()
    asyncio.run(main(args.url))
