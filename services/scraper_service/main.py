import os
import sys
import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Tuple

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

# In-memory search result cache (TTL: 10 minutes)
_SEARCH_CACHE: Dict[str, Tuple[float, SearchResponse]] = {}
CACHE_TTL = 600

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "scraper-service"}

@app.post("/scrape", response_model=ScrapeResult)
async def scrape_url(task: ScrapeTask):
    logger.info(f"Scraping URL: {task.url} using {task.scraper_type}")
    try:
        def _run_scraper():
            scraper = Scraper(
                urls=[task.url],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                scraper=task.scraper_type
            )
            # Run scraper synchronously in threadpool if not coroutine
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                return loop.run_until_complete(scraper.run())
            except Exception:
                return []

        content_list = await asyncio.to_thread(_run_scraper)
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
    cache_key = f"{query.retriever.lower()}:{query.query.strip().lower()}:{query.max_results}"
    now = time.time()
    
    # Check cache
    if cache_key in _SEARCH_CACHE:
        timestamp, cached_res = _SEARCH_CACHE[cache_key]
        if now - timestamp < CACHE_TTL:
            logger.info(f"Cache hit for search query: '{query.query}'")
            return cached_res

    logger.info(f"Search request: '{query.query}' using retriever '{query.retriever}'")
    retriever_cls = RETRIEVER_MAP.get(query.retriever.lower()) or TavilySearch
    try:
        retriever = retriever_cls(query.query)
        search_fn = retriever.search
        
        # Run blocking search on threadpool to prevent freezing the event loop
        if asyncio.iscoroutinefunction(search_fn):
            results = await search_fn(max_results=query.max_results)
        else:
            results = await asyncio.to_thread(search_fn, max_results=query.max_results)
        
        items = []
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict):
                    items.append(SearchResultItem(
                        title=r.get("title", ""),
                        url=r.get("url", "") or r.get("href", ""),
                        content=r.get("content", "") or r.get("body", ""),
                        raw_content=r.get("raw_content", None),
                        score=r.get("score", None)
                    ))
        response = SearchResponse(query=query.query, retriever=query.retriever, results=items)
        _SEARCH_CACHE[cache_key] = (now, response)
        return response
    except Exception as e:
        logger.error(f"Search error for '{query.query}': {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SCRAPER_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
