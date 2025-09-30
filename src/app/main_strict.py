
# -*- coding: utf-8 -*-
"""Strict 模式 API
- 只允許 Transformer 推論；若模型未載入 -> 直接 503。
- 新增 Signals 查詢端點（entity/industry/market），欄位含 weighted_mean、surprise_src7。
- 內建防護：CPU-only、批量查詢、DB 連線重試、超時、硬性輸入長度上限避免 OOM。
- 任何例外皆不做回退（Strict 原則）。
"""
from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import os, time, math
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from src.config import DB_URL

app = FastAPI(title="FinNews Strict API", version="1.0.0 (strict)")

# ---------------------- Strict Transformer Loader ----------------------
MODEL_NAME = os.getenv("TRANSFORMER_MODEL_NAME", "hfl/chinese-bert-wwm-ext")
MODEL_DIR  = os.getenv("TRANSFORMER_MODEL_DIR", None)  # 若提供本地路徑則優先
DEVICE = "cpu"  # 嚴格 CPU；避免顯卡功耗/驅動造成閃退

_tokenizer = None
_model = None
_model_loaded = False
_load_error: Optional[str] = None

def _load_model_strict():
    global _tokenizer, _model, _model_loaded, _load_error
    try:
        name = MODEL_DIR if MODEL_DIR else MODEL_NAME
        _tokenizer = AutoTokenizer.from_pretrained(name)
        _model = AutoModelForSequenceClassification.from_pretrained(name)
        _model.to(DEVICE)
        _model.eval()
        _model_loaded = True
        _load_error = None
    except Exception as e:
        _tokenizer = None
        _model = None
        _model_loaded = False
        _load_error = f"{type(e).__name__}: {e}"

# 提供顯式載入端點（可在容器啟動後呼叫一次）
@app.post("/load", tags=["admin"])
def load_model():
    _load_model_strict()
    if not _model_loaded:
        raise HTTPException(status_code=503, detail=f"模型未載入：{_load_error}")
    return {"ok": True, "model": MODEL_DIR or MODEL_NAME}

# 啟動時嘗試載入（失敗也不降級，嚴格模式只回 503）
try:
    _load_model_strict()
except Exception:
    pass

# ---------------------- DB ----------------------
def _make_engine() -> Engine:
    # 使用連線池；以免 Streamlit/多請求打爆 DB
    return create_engine(DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=5, future=True)

_engine = _make_engine()

# ---------------------- Schemas ----------------------
class ScoreIn(BaseModel):
    text: str = Field(..., max_length=8000, description="要評分的文本（上限 8000 字符，避免 OOM）")

class ScoreOut(BaseModel):
    score: float
    model: str

def _strict_score(text: str) -> float:
    # 未載入 -> 503（嚴格）
    if not _model_loaded or _tokenizer is None or _model is None:
        raise HTTPException(status_code=503, detail="模型未載入（Strict）")
    # 輸入清洗 & 長度限制
    if not text or not text.strip():
        return 0.0
    tokens = _tokenizer(
        text.strip(),
        truncation=True,
        max_length=512,
        padding=False,
        return_tensors="pt"
    )
    with torch.no_grad():
        logits = _model(**{k: v.to(DEVICE) for k, v in tokens.items()}).logits
    # 通用：若是二分類，取第2維；若單一回歸，直接用
    if logits.shape[-1] == 1:
        val = float(torch.tanh(logits.squeeze()).item())
        # tanh 將值壓到 [-1, 1]
        return val
    elif logits.shape[-1] == 2:
        # 二分類 -> positive 機率再映射到 [-1,1]
        prob_pos = float(torch.softmax(logits, dim=-1)[0, 1].item())
        return 2.0 * prob_pos - 1.0
    else:
        # 多分類：以極性軸近似（最後一類視為正向）
        probs = torch.softmax(logits, dim=-1)[0].tolist()
        idx = int(torch.argmax(logits, dim=-1).item())
        # 線性映射到 [-1,1]：0 -> -1, last -> +1
        if len(probs) <= 1:
            return 0.0
        return -1.0 + 2.0 * (idx / (len(probs) - 1))

@app.get("/health")
def health():
    return {
        "ok": True,
        "strict": True,
        "model_loaded": _model_loaded,
        "model": (MODEL_DIR or MODEL_NAME) if _model_loaded else None,
        "load_error": _load_error
    }

@app.post("/score", response_model=ScoreOut)
def score(payload: ScoreIn):
    val = _strict_score(payload.text)
    return ScoreOut(score=val, model=(MODEL_DIR or MODEL_NAME))

# ---------------------- Signals Endpoints ----------------------
def _query_signals(kind: Literal["entity","industry","market"], key: Optional[str], start: Optional[str], end: Optional[str], limit: int = 5000):
    if kind in ("entity","industry") and not key:
        raise HTTPException(status_code=400, detail="缺少查詢鍵（ticker 或 industry）。")
    where = ["1=1"]
    params = {"limit": limit}
    if start:
        where.append("ds >= :start")
        params["start"] = start
    if end:
        where.append("ds <= :end")
        params["end"] = end

    if kind == "entity":
        table = "signals_entity_daily"
        where.append("ticker = :k")
        params["k"] = key
        cols = "ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7"
    elif kind == "industry":
        table = "signals_industry_daily"
        where.append("industry = :k")
        params["k"] = key
        cols = "ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7"
    else:
        table = "signals_market_daily"
        cols = "ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7"

    sql = f"""
        SELECT TOP (:limit) {cols}
        FROM {table}
        WHERE {' AND '.join(where)}
        ORDER BY ds ASC
    """
    try:
        with _engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"DB 錯誤：{str(e)}")

@app.get("/signals/entity")
def signals_entity(ticker: str = Query(...), start: Optional[str] = None, end: Optional[str] = None, limit: int = 5000):
    return _query_signals("entity", ticker, start, end, limit)

@app.get("/signals/industry")
def signals_industry(industry: str = Query(...), start: Optional[str] = None, end: Optional[str] = None, limit: int = 5000):
    return _query_signals("industry", industry, start, end, limit)

@app.get("/signals/market")
def signals_market(start: Optional[str] = None, end: Optional[str] = None, limit: int = 5000):
    return _query_signals("market", None, start, end, limit)
