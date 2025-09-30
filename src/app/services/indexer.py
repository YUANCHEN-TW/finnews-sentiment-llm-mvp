# 簡化的情緒指數聚合
from sqlalchemy import text
import pandas as pd
from src.app.storage.db import get_engine

def daily_market_index():
    engine = get_engine()
    df = pd.read_sql(text("SELECT title, content FROM news"), engine)
    if df.empty:
        return 0.0
    pos = df["title"].str.contains("利多|創新高|看多|上修", regex=True).sum()
    neg = df["title"].str.contains("利空|下修|大跌|看空|降評", regex=True).sum()
    total = max(1, pos + neg)
    return (pos - neg) / total
