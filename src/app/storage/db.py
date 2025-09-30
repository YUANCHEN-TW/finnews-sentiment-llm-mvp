from sqlalchemy import create_engine
from src.config import DB_URL

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DB_URL, future=True)
    return _engine
