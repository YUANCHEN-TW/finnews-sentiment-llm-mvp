
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict
import yaml
import jieba

@dataclass
class RuleConfig:
    positive: List[str]
    negative: List[str]
    negations: List[str]
    intensifiers: List[str]
    dampeners: List[str]

def load_lexicon(path: str) -> RuleConfig:
    with open(path, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    return RuleConfig(
        positive=y.get("positive", []),
        negative=y.get("negative", []),
        negations=y.get("negations", []),
        intensifiers=y.get("intensifiers", []),
        dampeners=y.get("dampeners", []),
    )

def tokenize_zh(text: str) -> List[str]:
    return [t.strip() for t in jieba.lcut(text) if t.strip()]

def _hits(tokens: List[str], vocab: List[str]) -> List[str]:
    vs = set(vocab)
    return [t for t in tokens if t in vs]

def score_sentence_zh(sent: str, cfg: RuleConfig) -> Tuple[int, Dict]:
    tokens = tokenize_zh(sent)
    pos_hits = _hits(tokens, cfg.positive)
    neg_hits = _hits(tokens, cfg.negative)
    negator_hits = _hits(tokens, cfg.negations)
    intens_hits = _hits(tokens, cfg.intensifiers)
    damp_hits = _hits(tokens, cfg.dampeners)

    score = len(pos_hits) - len(neg_hits)
    if negator_hits and score != 0:
        score = -score
    score += min(len(intens_hits), 2)
    score -= min(len(damp_hits), 2)
    score = max(-3, min(3, score))

    label = 0
    if score > 0:
        label = 1
    elif score < 0:
        label = -1

    info = {
        "tokens": tokens,
        "pos_hits": pos_hits,
        "neg_hits": neg_hits,
        "negations": negator_hits,
        "intensifiers": intens_hits,
        "dampeners": damp_hits,
        "raw_score": score,
    }
    return label, info
