from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Unicode, UnicodeText, DateTime, Float, UniqueConstraint

Base = declarative_base()

class News(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint('url', name='uq_news_url'),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Unicode(512))
    content = Column(UnicodeText)
    source = Column(Unicode(128))
    url = Column(Unicode(512))
    published_at = Column(DateTime)
    created_at = Column(DateTime)

class Price(Base):
    __tablename__ = "price"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Unicode(16))
    date = Column(DateTime)
    close = Column(Float)
