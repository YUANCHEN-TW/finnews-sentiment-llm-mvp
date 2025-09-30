# 弱監督：簡單情緒詞典（示範）
POS = ["成長", "上修", "利多", "創新高", "優於預期", "看多", "增持", "超預期"]
NEG = ["下修", "利空", "重挫", "大跌", "裁員", "看空", "降評", "虧損"]

def weak_label(text: str) -> int:
    t = str(text)
    score = 0
    for w in POS:
        if w in t:
            score += 1
    for w in NEG:
        if w in t:
            score -= 1
    if score > 0:
        return 1
    if score < 0:
        return -1
    return 0
