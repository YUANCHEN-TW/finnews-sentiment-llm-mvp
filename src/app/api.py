# -*- coding: utf-8 -*-
"""
FastAPI — 產品化 API（含 /score /index/{date} /report/{date} — 完整版）
"""
import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Any
from src.llm import rag_report_gemini as rag

app = FastAPI(title="FinNews Sentiment API", version="0.1.2")

def _transformer_ready() -> bool:
    """嚴格模式：環境變數或 runtime.is_ready() 二擇一為真"""
    if os.environ.get("TRANSFORMER_READY","0") == "1":
        return True
    try:
        from src.models import runtime as rt
        if hasattr(rt, "is_ready") and callable(rt.is_ready):
            return bool(rt.is_ready())
    except Exception:
        pass
    return False

# ---------- /score ----------
class ScoreReq(BaseModel):
    text: str

class ScoreResp(BaseModel):
    score: float

@app.post("/score", response_model=ScoreResp)
def score(req: ScoreReq):
    if not _transformer_ready():
        raise HTTPException(status_code=503, detail="模型未載入")
    try:
        from src.models import runtime as rt
        if not hasattr(rt, "score_text") or not callable(rt.score_text):
            raise HTTPException(status_code=500, detail="runtime.score_text 不可用")
        s = float(rt.score_text(req.text))
        return ScoreResp(score=s)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"評分失敗: {e}")

# ---------- /index/{date} ----------
class IndexItem(BaseModel):
    news_id: Any
    title: str
    source: str
    url: str
    pub_ts: str
    doc_score: float
    rank: float

class IndexResp(BaseModel):
    date: str
    top_k: int
    items: List[IndexItem]

@app.get("/index/{dt}", response_model=IndexResp)
def get_index(dt: str, top_k: int = Query(default=8, ge=1, le=int(os.environ.get("RAG_TOPK_MAX","12")))):
    try:
        items = rag._fetch_top_news(dt, top_k=top_k)
        out = [IndexItem(
            news_id=it.get("news_id"),
            title=it.get("title",""),
            source=it.get("source",""),
            url=it.get("url",""),
            pub_ts=str(it.get("pub_ts")),
            doc_score=float(it.get("doc_score",0.0)),
            rank=float(it.get("rank",0.0))
        ) for it in items]
        return IndexResp(date=dt, top_k=top_k, items=out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引失敗: {e}")

# ---------- /report/{date} ----------
class ReportResp(BaseModel):
    date: str
    top_k: int
    report: str

@app.get("/report/{dt}", response_model=ReportResp)
def get_report(dt: str, top_k: int = Query(default=8, ge=1, le=int(os.environ.get("RAG_TOPK_MAX","12")))):
    if not _transformer_ready():
        raise HTTPException(status_code=503, detail="模型未載入")
    try:
        txt = rag.generate_daily_report(dt, top_k=top_k)
        return ReportResp(date=dt, top_k=top_k, report=txt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失敗: {e}")