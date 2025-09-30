import os, joblib
from src.config import MODEL_DIR
os.makedirs(MODEL_DIR, exist_ok=True)

def save_model(model, name: str):
    path = os.path.join(MODEL_DIR, f"{name}.joblib")
    joblib.dump(model, path)
    return path

def load_model(name: str):
    path = os.path.join(MODEL_DIR, f"{name}.joblib")
    if not os.path.exists(path):
        return None
    import joblib
    return joblib.load(path)
