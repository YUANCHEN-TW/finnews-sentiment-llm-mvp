# 使用已保存的 baseline 模型；若無則退化到弱監督詞典
from typing import Tuple
import numpy as np
from src.models.registry import load_model
from src.etl.label_weak import weak_label

_model = load_model("baseline_tfidf_logreg")

def score(text: str) -> Tuple[str, float]:
    if _model is not None:
        proba = _model.predict_proba([text])[0]
        idx = int(np.argmax(proba))
        label = "positive" if idx == 1 else "negative"
        return label, float(proba[idx])
    # fallback：弱監督
    y = weak_label(text)
    if y > 0:
        return "positive", 0.6
    elif y < 0:
        return "negative", 0.6
    return "neutral", 0.5
