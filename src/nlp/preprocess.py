from dataclasses import dataclass
from typing import List
import re
from langdetect import detect, DetectorFactory
from opencc import OpenCC

DetectorFactory.seed = 0
cc = OpenCC('s2t')

def normalize_whitespace(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text).replace("\u3000", " ").replace("\xa0", " ")).strip()
    return t

def strip_boilerplate(text: str) -> str:
    return text

def clean_text(text: str) -> str:
    t = normalize_whitespace(text)
    t = strip_boilerplate(t)
    return t

def detect_lang(text: str) -> str:
    try:
        lg = detect(text)
        if lg.startswith("zh"):
            return "zh"
        return lg
    except Exception:
        return "unknown"

def convert_zh(text: str) -> str:
    try:
        return cc.convert(text)
    except Exception:
        return text

@dataclass
class PreprocResult:
    lang: str
    cleaned: str
    sentences: List[str]

def preprocess_document(title: str, content: str) -> PreprocResult:
    raw = f"{title or ''}。{content or ''}".strip("。")
    raw = clean_text(raw)
    lang = detect_lang(raw) if raw else "unknown"
    if lang == "zh":
        raw = convert_zh(raw)
    from .sent_tokenize import split_any
    sents = split_any(raw, lang)
    return PreprocResult(lang=lang, cleaned=raw, sentences=sents)
