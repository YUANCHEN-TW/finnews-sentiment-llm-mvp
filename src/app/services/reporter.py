from src.llm.generate_report import render_daily_report
from src.app.services.indexer import daily_market_index

def generate_daily_report():
    idx = daily_market_index()
    return render_daily_report(market_index=idx)
