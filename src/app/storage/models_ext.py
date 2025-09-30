from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Unicode, UnicodeText, DateTime

Base = declarative_base()

class NewsProc(Base):
    __tablename__ = "news_proc"
    id = Column(Integer, primary_key=True, autoincrement=True)
    news_id = Column(Integer, index=True)  # 參照 news.id
    lang = Column(Unicode(16))
    cleaned = Column(UnicodeText)
    sentences_json = Column(UnicodeText)   # JSON 字串
    created_at = Column(DateTime)
