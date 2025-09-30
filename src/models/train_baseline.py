# Baseline：TF-IDF + Logistic Regression，使用弱監督標註
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
from src.config import DB_URL
from src.etl.label_weak import weak_label
from src.models.registry import save_model

def load_news(limit=1000):
    engine = create_engine(DB_URL, future=True)
    q = text("SELECT id, title, content FROM news ORDER BY published_at DESC")
    df = pd.read_sql(q, engine)
    df["text"] = (df["title"].fillna("") + " " + df["content"].fillna("")).str.strip()
    df["y"] = df["text"].map(weak_label)  # -1, 0, 1
    df = df[df["y"] != 0]  # 先做二分類（正/負）
    df["y"] = (df["y"] == 1).astype(int)
    return df

def main():
    df = load_news()
    if len(df) < 2:
        print("資料過少，請先增加新聞資料。")
        return
    pipe = Pipeline([
        # 這裡改成「字元 n-gram」以支援中文
        ("tfidf", TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),   # 抓「利多」「大幅下修」等 2~4 字片段
            max_features=5000
        )),
        ("clf", LogisticRegression(max_iter=300)),
    ])
    pipe.fit(df["text"], df["y"])
    preds = pipe.predict(df["text"])
    print(classification_report(df["y"], preds, digits=3))
    path = save_model(pipe, "baseline_tfidf_logreg")
    print("Saved model to:", path)

if __name__ == "__main__":
    main()
