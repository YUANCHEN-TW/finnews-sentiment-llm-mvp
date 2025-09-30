from sqlalchemy import create_engine, text
from src.config import DB_URL

def main():
    print("DB_URL =", DB_URL)
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        try:
            v = conn.execute(text("SELECT @@VERSION")).scalar()
            print("SQL Server version =>\n", v)
        except Exception as e:
            print("無法查詢 @@VERSION：", e)

        conn.execute(text("IF OBJECT_ID('tempdb..#t') IS NOT NULL DROP TABLE #t; CREATE TABLE #t (id INT); INSERT INTO #t VALUES (1);"))
        n = conn.execute(text("SELECT COUNT(*) FROM #t")).scalar()
        print("臨時表 #t 筆數 =", n)

if __name__ == "__main__":
    main()
