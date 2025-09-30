from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from src.llm.prompt_templates import DAILY_REPORT_TEMPLATE
from src.llm.rag import topk_news

@dataclass
class Ref:
    title: str
    source: str
    url: str
    published_at: str

def render_daily_report(market_index: float = 0.0):
    news = topk_news(5)
    references = [Ref(n['title'], n['source'], n['url'], str(n['published_at'])) for n in news]
    # 簡化：示範填充
    html = DAILY_REPORT_TEMPLATE.render(
        date=datetime.utcnow().date().isoformat(),
        market_index=f"{market_index:.2f}",
        surprises=[n['title'] for n in news],
        highlights={"半導體": [news[0]['title']] if news else []},
        references=references
    )
    return html
