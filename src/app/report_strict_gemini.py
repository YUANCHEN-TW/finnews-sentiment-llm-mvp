# -*- coding: utf-8 -*-
"""
/report（Strict 版）— 使用 Google Gemini 生成，但嚴格依賴「已載入的 Transformer 分數」。
- 若未載入分類器（Transformer），直接回 503 並提示「模型未載入」。
- 僅在 Transformer 可用時，才會檢索 Top-K 並生成報告。
- 防護：限制 K、限制超時、加入 try/except 避免伺服器因例外而崩潰。
"""
import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from src.llm.rag_report_gemini import generate_daily_report
from datetime import date

app = FastAPI()

def _transformer_ready() -> bool:
    if os.environ.get("TRANSFORMER_READY","0") == "1":
        return True
    try:
        from src.models import runtime as rt
        if hasattr(rt, "is_ready") and callable(rt.is_ready):
            return bool(rt.is_ready())
    except Exception:
        pass
    return False

class ReportResp(BaseModel):
    date: str
    top_k: int
    report: str

@app.get("/report", response_model=ReportResp)
def report(date_str: str = Query(default=None, description="報告日期 YYYY-MM-DD，預設今天"),
           top_k: int = Query(default=8, ge=1, le=12)):
    if not _transformer_ready():
        raise HTTPException(status_code=503, detail="模型未載入")

    d = date_str or date.today().isoformat()
    try:
        txt = generate_daily_report(d, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失敗: {e}")
    return ReportResp(date=d, top_k=top_k, report=txt)
