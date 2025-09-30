# 簡化：規則式抽取公司與代碼（MVP 版，可改為更強 NER）
import re
from typing import List, Dict

COMPANY_DICT = {
    "台積電": "2330",
    "聯發科": "2454",
    "鴻海": "2317",
    "國泰金": "2882",
}

def extract_entities(text: str) -> Dict[str, List[str]]:
    found = []
    for k, v in COMPANY_DICT.items():
        if k in text:
            found.append((k, v))
    # 也嘗試用代碼匹配
    codes = re.findall(r"\b\d{4}\b", text)
    for c in codes:
        found.append(("UNKNOWN", c))
    res = {"companies": list({name for name,_ in found}), "codes": list({code for _,code in found})}
    return res
