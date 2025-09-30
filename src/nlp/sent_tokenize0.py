import re
from typing import List

ZH_SPLIT_RE = re.compile(r"(?<=[。！？；]|\.{3,}|…)(?=\s*[^\d])")

def split_zh(text: str) -> List[str]:
    t = str(text).strip()
    if not t:
        return []
    sents = [s.strip() for s in ZH_SPLIT_RE.split(t) if s.strip()]
    return sents

def split_en(text: str) -> List[str]:
    try:
        from nltk.tokenize import sent_tokenize
        return [s.strip() for s in sent_tokenize(text) if s.strip()]
    except Exception:
        return [text.strip()] if text else []

def split_any(text: str, lang: str) -> List[str]:
    if lang.startswith("zh"):
        return split_zh(text)
    return split_en(text)
