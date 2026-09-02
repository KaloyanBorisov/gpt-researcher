import os
import sys
import logging
import asyncio
import httpx
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import SectionResearchRequest, SectionResearchResponse
from services.common.config import settings
from gpt_researcher.utils.llm import create_chat_completion
from gpt_researcher.config import Config

logger = logging.getLogger("section_research_service")

class SectionResearchWorker:
    """Specialized worker service for executing fast, concurrent research on a subtopic."""

    async def research_section(self, request: SectionResearchRequest) -> SectionResearchResponse:
        logger.info(f"Conducting concurrent section research for subtopic: '{request.subtopic}'")
        cfg = Config()

        child_run = None
        callbacks = []
        if request.parent_run_id and (os.getenv("LANGCHAIN_TRACING_V2") == "true" or os.getenv("LANGSMITH_TRACING") == "true"):
            try:
                from langsmith.run_trees import RunTree
                child_run = RunTree(
                    name=f"Section Research: {request.subtopic[:40]}",
                    run_type="chain",
                    parent_run_id=request.parent_run_id,
                    inputs={"task": request.task, "subtopic": request.subtopic, "subqueries": request.subqueries},
                    project_name=os.getenv("LANGSMITH_PROJECT", "gpt-researcher")
                )
                child_run.post()
                callbacks = [child_run.get_langchain_callback()]
            except Exception as tr_err:
                logger.warning(f"Failed to create child RunTree for section worker: {tr_err}")

        queries = request.subqueries if request.subqueries else [f"{request.task} {request.subtopic}"]
        target_queries = queries[:3]  # Focus on top 3 most targeted queries

        async with httpx.AsyncClient(timeout=20.0) as client:
            async def fetch_for_query(q: str):
                ctx = []
                srcs = []
                try:
                    if request.report_source in ("local", "hybrid"):
                        doc_res = await client.post(f"{settings.DOCUMENT_URL}/query", json={"query": q, "top_k": 3})
                        if doc_res.status_code == 200:
                            for c in doc_res.json():
                                ctx.append(c.get("text", ""))
                                if "metadata" in c and "source" in c["metadata"]:
                                    srcs.append(c["metadata"]["source"])

                    if request.report_source in ("web", "hybrid"):
                        search_res = await client.post(
                            f"{settings.SCRAPER_URL}/search",
                            json={"query": q, "max_results": request.max_results_per_query or 3}
                        )
                        if search_res.status_code == 200:
                            for item in search_res.json().get("results", []):
                                ctx.append(item.get("content", ""))
                                url = item.get("url", "")
                                if url:
                                    srcs.append(url)
                except Exception as search_err:
                    logger.warning(f"Failed query '{q}': {search_err}")
                return ctx, srcs

            # Execute all queries concurrently in parallel
            query_results = await asyncio.gather(*[fetch_for_query(q) for q in target_queries])

        collected_context: List[str] = []
        scraped_sources: List[str] = []
        for ctx_list, src_list in query_results:
            collected_context.extend(ctx_list)
            scraped_sources.extend(src_list)

        unique_sources = list(dict.fromkeys(scraped_sources))
        raw_context_str = "\n\n---\n\n".join(collected_context[:8]) if collected_context else "No external context found."

        # 2. Synthesize section draft with fast LLM
        prompt = (
            f"You are a specialized research analyst. Write a concise, rigorous section for a research report.\n\n"
            f"Main Topic: \"{request.task}\"\n"
            f"Section Subtopic: \"{request.subtopic}\"\n"
            f"Tone: {request.tone}\n\n"
            f"Context / Findings:\n"
            f"{raw_context_str[:4000]}\n\n"
            f"Instructions:\n"
            f"- Provide key analytical insights with specific facts and figures.\n"
            f"- Cite sources where relevant.\n"
            f"- Keep it informative and well-structured with markdown."
        )

        messages = [
            {"role": "system", "content": "You are a specialized domain research analyst."},
            {"role": "user", "content": prompt}
        ]

        try:
            draft_content = await create_chat_completion(
                messages=messages,
                model=cfg.fast_llm_model,
                llm_provider=cfg.fast_llm_provider,
                temperature=0.35,
                max_tokens=2000,
                callbacks=callbacks
            )
        except Exception as llm_err:
            logger.error(f"Error drafting section: {llm_err}")
            draft_content = f"### {request.subtopic}\n\nAnalysis based on gathered context: {raw_context_str[:400]}..."

        response = SectionResearchResponse(
            subtopic=request.subtopic,
            context=raw_context_str[:3000],
            sources=unique_sources,
            draft_content=draft_content
        )

        if child_run:
            child_run.end(outputs={"subtopic": response.subtopic, "sources_count": len(response.sources), "draft_length": len(draft_content)})
            child_run.patch()

        return response

worker = SectionResearchWorker()
