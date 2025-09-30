import re

def basic_clean(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.replace("\u3000", " ").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()
