from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from src.config import DB_URL
from src.etl.clean import basic_clean
from src.app.storage.models import Base, News, Price

def main():
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, future=True)
    s = Session()

    now = datetime.utcnow()
    sample_news = [
        ("台積電法說會釋出利多 訂單可見度上修", "市場看多先進製程，資本支出維持高檔。", "DemoNews", "https://example.com/1", now - timedelta(hours=26)),
        ("聯發科下修全年財測 投資人情緒轉弱", "手機需求疲弱，毛利率承壓。", "DemoNews", "https://example.com/2", now - timedelta(hours=20)),
        ("鴻海營收創新高 迎來旺季動能", "雲端與AI伺服器需求推升。", "DemoNews", "https://example.com/3", now - timedelta(hours=5)),
    ]
    for t, c, src, url, ts in sample_news:
        s.add(News(title=basic_clean(t), content=basic_clean(c), source=src, url=url, published_at=ts, created_at=now))

    for i, code in enumerate(["2330", "2454", "2317"]):
        for d in range(7):
            s.add(Price(code=code, date=now - timedelta(days=7-d), close=500 + i*50 + d*2))
    try:
        s.commit()
        print("Seeded DB with demo news & prices at", DB_URL)
    except Exception as e:
        s.rollback()
        print("Error seeding:", e)
    finally:
        s.close()

if __name__ == "__main__":
    main()
