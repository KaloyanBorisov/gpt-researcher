import os
import sys
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import (
    ResearchRequest,
    PlanRequest,
    SectionResearchRequest,
    ReviewRequest,
    SynthesisRequest
)
from services.common.redis_pubsub import event_bus
from services.common.config import settings

logger = logging.getLogger("workflow_coordinator")

# Persistent connection pool for high-throughput microservice communication
http_limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
http_timeout = httpx.Timeout(60.0, connect=10.0)

class WorkflowCoordinator:
    """
    Coordinates distributed research workflows across specialized agent microservices:
    1. Planning Service (:8011)
    2. Section Research Worker Service (:8012)
    3. Reviewer & Quality Service (:8013)
    4. Writer & Synthesis Service (:8014)
    5. Export Service (:8004)
    """

    async def execute_research(self, request: ResearchRequest, session_id: str):
        channel = f"research:{session_id}"
        logger.info(f"Starting optimized distributed research for session {session_id}: '{request.task}'")

        async def websocket_event_emitter(event_type: str, content: Any = "", output: Any = "", metadata: Any = None):
            payload = {
                "type": event_type,
                "content": content if content is not None else "",
                "output": output if output is not None else content,
                "metadata": metadata if metadata is not None else {}
            }
            await event_bus.publish(channel, payload)

        try:
            # Clean up empty env strings
            for env_k in ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENROUTER_BASE_URL", "OPENROUTER_API_BASE", "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]:
                if env_k in os.environ and not os.environ[env_k].strip():
                    del os.environ[env_k]

            # 1. Starting research event
            await websocket_event_emitter(
                "logs",
                content="starting_research",
                output=f"🔍 Initializing high-speed distributed workflow for: '{request.task}'"
            )

            async with httpx.AsyncClient(limits=http_limits, timeout=http_timeout) as client:
                # -------------------------------------------------------------
                # 1. Fast Planning Phase (Planning Service :8011)
                # -------------------------------------------------------------
                await websocket_event_emitter(
                    "logs",
                    content="planning_research",
                    output=f"📊 [Planning Service] Formulating targeted research plan..."
                )
                
                max_subtopics = request.max_subtopics or 3
                plan_res = await client.post(
                    f"{settings.PLANNING_URL}/plan",
                    json={
                        "task": request.task,
                        "report_type": request.report_type,
                        "tone": request.tone,
                        "max_subtopics": max_subtopics
                    }
                )
                
                if plan_res.status_code == 200:
                    plan_data = plan_res.json()
                    subtopics = plan_data.get("subtopics", [])[:max_subtopics]
                    outline = plan_data.get("outline", [])
                else:
                    logger.warning(f"Planning service error ({plan_res.status_code}), using fallback plan.")
                    subtopics = [{"title": request.task, "subqueries": [request.task]}]
                    outline = ["Introduction", request.task, "Conclusion"]

                subquery_titles = [st.get("title", "") for st in subtopics]
                await websocket_event_emitter(
                    "logs",
                    content="subqueries",
                    output=subquery_titles,
                    metadata=subquery_titles
                )

                await websocket_event_emitter(
                    "logs",
                    content="agent_generated",
                    output=f"📋 [Planner] Plan formulated with {len(subtopics)} focused sections ({', '.join(subquery_titles)})"
                )

                # -------------------------------------------------------------
                # 2. Parallel Section Research Phase (Section Research Service :8012)
                # -------------------------------------------------------------
                await websocket_event_emitter(
                    "logs",
                    content="agent_generated",
                    output=f"🌐 [Section Researcher] Executing parallel research across {len(subtopics)} subtopics..."
                )

                seen_sources = set()

                async def research_single_section(st_dict):
                    title = st_dict.get("title", "")
                    queries = st_dict.get("subqueries", [title])
                    
                    try:
                        res = await client.post(
                            f"{settings.SECTION_RESEARCH_URL}/research-section",
                            json={
                                "task": request.task,
                                "subtopic": title,
                                "subqueries": queries,
                                "report_source": request.report_source,
                                "tone": request.tone,
                                "max_results_per_query": 3
                            }
                        )
                        if res.status_code == 200:
                            s_data = res.json()
                            for src in s_data.get("sources", []):
                                if src and src not in seen_sources:
                                    seen_sources.add(src)
                                    await websocket_event_emitter(
                                        "logs",
                                        content="added_source_url",
                                        output=src,
                                        metadata=src
                                    )

                            await websocket_event_emitter(
                                "logs",
                                content="agent_generated",
                                output=f"✅ Researched '{title}' ({len(s_data.get('sources', []))} sources)"
                            )
                            return s_data
                    except Exception as err:
                        logger.error(f"Error researching section '{title}': {err}")
                    
                    return {"subtopic": title, "context": "", "sources": [], "draft_content": f"### {title}\nAnalysis in progress."}

                # Execute all sections in parallel concurrently
                sections = await asyncio.gather(*[research_single_section(st) for st in subtopics])
                all_sources = list(seen_sources)

                # -------------------------------------------------------------
                # 3 & 4. Pipelined Review & Synthesis Phase
                # -------------------------------------------------------------
                await websocket_event_emitter(
                    "logs",
                    content="agent_generated",
                    output="✍️ [Writer Service] Synthesizing comprehensive research report..."
                )

                # Run Reviewer & Writer concurrently
                async def run_review():
                    try:
                        review_res = await client.post(
                            f"{settings.REVIEWER_URL}/review",
                            json={
                                "task": request.task,
                                "content": "\n\n".join([s.get("draft_content", "") for s in sections]),
                                "sources": all_sources
                            }
                        )
                        if review_res.status_code == 200:
                            r_data = review_res.json()
                            score = r_data.get("score", 1.0)
                            await websocket_event_emitter(
                                "logs",
                                content="agent_generated",
                                output=f"⭐ [Reviewer Score: {int(score * 100)}%] {r_data.get('feedback', 'Passed review.')}"
                            )
                    except Exception as rev_err:
                        logger.warning(f"Reviewer check warning: {rev_err}")

                async def run_synthesis():
                    synth_res = await client.post(
                        f"{settings.WRITER_URL}/synthesize",
                        json={
                            "task": request.task,
                            "report_type": request.report_type,
                            "tone": request.tone,
                            "outline": outline,
                            "sections": sections,
                            "sources": all_sources
                        }
                    )
                    if synth_res.status_code == 200:
                        return synth_res.json().get("report_markdown", "")
                    return f"# {request.task}\n\n" + "\n\n".join([s.get("draft_content", "") for s in sections])

                # Execute review and report synthesis in parallel
                _, report = await asyncio.gather(run_review(), run_synthesis())

                # -------------------------------------------------------------
                # 5. Concurrent Document Export Phase (Export Service :8004)
                # -------------------------------------------------------------
                paths = {}
                async def export_format(fmt: str):
                    try:
                        res = await client.post(f"{settings.EXPORT_URL}/export", json={
                            "report_markdown": report,
                            "title": request.task[:50],
                            "format": fmt
                        })
                        if res.status_code == 200:
                            data = res.json()
                            return (fmt if fmt != "markdown" else "md", data.get("download_url"))
                    except Exception as exp_err:
                        logger.warning(f"Export error for {fmt}: {exp_err}")
                    return (fmt if fmt != "markdown" else "md", None)

                # Export all formats concurrently in parallel
                export_results = await asyncio.gather(*[export_format(fmt) for fmt in ["markdown", "pdf", "docx"]])
                for fmt_key, download_url in export_results:
                    if download_url:
                        paths[fmt_key] = download_url

                # -------------------------------------------------------------
                # 6. Publish Final Output
                # -------------------------------------------------------------
                await event_bus.publish(channel, {
                    "type": "report",
                    "content": "report",
                    "output": report,
                    "metadata": {"sources_count": len(all_sources)}
                })

                await event_bus.publish(channel, {
                    "type": "path",
                    "content": "path",
                    "output": paths
                })

                await websocket_event_emitter(
                    "logs",
                    content="agent_generated",
                    output="🎉 Research report successfully synthesized and exported!"
                )

                return {
                    "session_id": session_id,
                    "status": "completed",
                    "report": report,
                    "sources": all_sources,
                    "paths": paths
                }

        except Exception as e:
            logger.error(f"Error during distributed research execution for {session_id}: {e}", exc_info=True)
            await websocket_event_emitter("error", content="error", output=f"Research failed: {str(e)}")
            return {
                "session_id": session_id,
                "status": "failed",
                "error": str(e)
            }

orchestrator = WorkflowCoordinator()
