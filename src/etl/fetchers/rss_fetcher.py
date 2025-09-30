# RSS 爬取範例（僅骨架，實務請加入來源、重試、去重、robots 檢查）
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict

async def fetch_rss(url: str) -> List[Dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")
        items = []
        for item in soup.select("item"):
            items.append({
                "title": item.title.text if item.title else "",
                "link": item.link.text if item.link else "",
                "pubDate": item.pubDate.text if item.pubDate else "",
                "description": item.description.text if item.description else "",
            })
        return items
