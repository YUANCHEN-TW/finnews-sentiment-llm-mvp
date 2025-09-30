# 簡化版 RAG：從資料庫取當日 Top-K 新聞
from sqlalchemy import create_engine, text
from src.config import DB_URL
import pandas as pd

def topk_news(k=5):
    engine = create_engine(DB_URL, future=True)
    df = pd.read_sql(text("SELECT title, content, source, url, published_at FROM news ORDER BY published_at DESC LIMIT :k"),
                     engine, params={"k": k})
    return df.to_dict(orient="records")
