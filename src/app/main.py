from fastapi import FastAPI
from src.app.schemas import ScoreRequest, ScoreResponse, ReportResponse
from src.app.services.scorer import score
from src.app.services.reporter import generate_daily_report

app = FastAPI(title="FinNews Sentiment & LLM Report (MVP)")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/score", response_model=ScoreResponse)
def score_text(req: ScoreRequest):
    label, prob = score(req.text)
    return ScoreResponse(label=label, prob=prob)

@app.get("/report/{date}", response_model=ReportResponse)
def get_report(date: str):
    # MVP：忽略日期，返回當日生成樣本
    html = generate_daily_report()
    return ReportResponse(html=html)
