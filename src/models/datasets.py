import os
import pandas as pd
from typing import Dict
from dataclasses import dataclass

@dataclass
class SplitPaths:
    train: str
    val: str
    test: str

def default_paths(root: str = "data/processed/dataset_v1") -> SplitPaths:
    return SplitPaths(
        train=os.path.join(root, "train.csv"),
        val=os.path.join(root, "val.csv"),
        test=os.path.join(root, "test.csv"),
    )

def load_splits(paths: SplitPaths) -> Dict[str, pd.DataFrame]:
    dfs = {}
    for k, p in paths.__dict__.items():
        if not os.path.exists(p):
            raise FileNotFoundError(f"Dataset split not found: {p}")
        df = pd.read_csv(p, encoding="utf-8-sig")
        if "gold_label" in df.columns:
            df["label"] = df["gold_label"]
        elif "rule_label" in df.columns:
            df["label"] = df["rule_label"]
        else:
            raise ValueError("CSV must contain gold_label or rule_label column.")
        if "sentence" not in df.columns:
            raise ValueError("CSV must contain 'sentence' column.")
        df = df[["sentence", "label"]].dropna()
        dfs[k] = df
    return dfs
