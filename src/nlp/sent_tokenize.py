import re
from typing import List

def _normalize_ellipsis(text: str) -> str:
    return text.replace("...", "…").replace("。。", "。")

_ZH_SENT_RE = re.compile(r"[^。！？；…\n]+[。！？；…]+|[^。！？；…\n]+$", re.U)

def split_zh(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    t = _normalize_ellipsis(text.strip())
    if not t:
        return []
    parts = _ZH_SENT_RE.findall(t)
    return [p.strip() for p in parts if p and p.strip()]

def split_en(text: str) -> List[str]:
    try:
        from nltk.tokenize import sent_tokenize
        return [s.strip() for s in sent_tokenize(text) if s.strip()]
    except Exception:
        return [text.strip()] if text else []

def split_any(text: str, lang: str) -> List[str]:
    if (lang or "").startswith("zh"):
        return split_zh(text)
    return split_en(text)
