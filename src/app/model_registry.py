import os
from typing import Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import threading

# Singleton-like registry
_LOCK = threading.Lock()
_TOKENIZER = None
_MODEL = None
_MODEL_DIR = None

def load_transformer(model_dir: Optional[str] = None):
    """Load transformer model/tokenizer from a directory. No fallback allowed."""
    global _TOKENIZER, _MODEL, _MODEL_DIR
    with _LOCK:
        if model_dir is None:
            model_dir = os.getenv("MODEL_DIR", "models/bert_sentence_cls")
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(f"模型目錄不存在：{model_dir}")
        _TOKENIZER = AutoTokenizer.from_pretrained(model_dir)
        _MODEL = AutoModelForSequenceClassification.from_pretrained(model_dir)
        _MODEL.eval()
        _MODEL_DIR = model_dir
        return _MODEL_DIR

def is_loaded() -> bool:
    return _MODEL is not None and _TOKENIZER is not None

def predict(text: str, max_length: int = 128):
    """Strict mode predict. Must have been loaded; otherwise raise RuntimeError."""
    if not is_loaded():
        raise RuntimeError("Transformer 模型尚未載入")
    import torch
    inputs = _TOKENIZER(text, return_tensors="pt", truncation=True, max_length=max_length)
    with torch.no_grad():
        out = _MODEL(**inputs)
        probs = torch.softmax(out.logits, dim=-1).squeeze(0).tolist()
        pred = int(torch.argmax(out.logits, dim=-1).item())
    id2label = {0:"neg", 1:"neu", 2:"pos"}
    return {"pred": id2label[pred], "probs": {"neg": probs[0], "neu": probs[1], "pos": probs[2]}}

def get_model_dir() -> Optional[str]:
    return _MODEL_DIR
