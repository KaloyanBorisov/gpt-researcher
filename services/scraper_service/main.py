import os
import sys
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ScrapeTask, ScrapeResult, SearchQuery, SearchResponse, SearchResultItem
from gpt_researcher.scraper.scraper import Scraper
from gpt_researcher.retrievers import TavilySearch, Duckduckgo, SearxSearch, GoogleSearch, BingSearch, ArxivSearch, ExaSearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("scraper_service")

app = FastAPI(title="GPT Researcher - Web Scraping & Search Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RETRIEVER_MAP = {
    "tavily": TavilySearch,
    "duckduckgo": Duckduckgo,
    "searx": SearxSearch,
    "google": GoogleSearch,
    "bing": BingSearch,
    "arxiv": ArxivSearch,
    "exa": ExaSearch,
}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "scraper-service"}

@app.post("/scrape", response_model=ScrapeResult)
async def scrape_url(task: ScrapeTask):
    logger.info(f"Scraping URL: {task.url} using {task.scraper_type}")
    try:
        scraper = Scraper(
            urls=[task.url],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            scraper=task.scraper_type
        )
        content_list = await scraper.run()
        if content_list and len(content_list) > 0:
            item = content_list[0]
            raw_text = item.get("raw_content", "") or item.get("body", "")
            title = item.get("title", "")
            return ScrapeResult(
                url=task.url,
                title=title,
                content=raw_text[:task.max_length] if task.max_length else raw_text,
                status="success"
            )
        else:
            return ScrapeResult(url=task.url, content="", status="empty")
    except Exception as e:
        logger.error(f"Error scraping {task.url}: {e}")
        return ScrapeResult(url=task.url, content="", status="error", error=str(e))

@app.post("/search", response_model=SearchResponse)
async def search(query: SearchQuery):
    logger.info(f"Search request: '{query.query}' using retriever '{query.retriever}'")
    retriever_cls = RETRIEVER_MAP.get(query.retriever.lower()) or TavilySearch
    try:
        retriever = retriever_cls(query.query)
        search_fn = retriever.search
        raw_res = search_fn(max_results=query.max_results)
        if asyncio.iscoroutine(raw_res):
            results = await raw_res
        else:
            results = raw_res
        
        items = []
        for r in results:
            items.append(SearchResultItem(
                title=r.get("title", ""),
                url=r.get("url", "") or r.get("href", ""),
                content=r.get("content", "") or r.get("body", ""),
                raw_content=r.get("raw_content", None),
                score=r.get("score", None)
            ))
        return SearchResponse(query=query.query, retriever=query.retriever, results=items)
    except Exception as e:
        logger.error(f"Search error for '{query.query}': {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SCRAPER_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
