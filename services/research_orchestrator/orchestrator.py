import os
import sys
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ResearchRequest, ResearchEvent
from services.common.redis_pubsub import event_bus
from services.common.config import settings
from gpt_researcher import GPTResearcher
from gpt_researcher.utils.enum import Tone, ReportType, ReportSource

logger = logging.getLogger("research_orchestrator")

class ResearchOrchestrator:
    """
    Coordinates and executes deep research workflows.
    Emits real-time event updates over the event bus (Redis Pub/Sub).
    """

    async def execute_research(self, request: ResearchRequest, session_id: str):
        channel = f"research:{session_id}"
        logger.info(f"Starting research for session {session_id}: {request.task}")

        async def websocket_event_emitter(event_type: str, content: Any = "", output: Any = "", metadata: Any = None):
            payload = {
                "type": event_type,
                "content": content or output,
                "output": output or content,
                "metadata": metadata if metadata is not None else {}
            }
            await event_bus.publish(channel, payload)

        try:
            # Clean up empty env strings so OpenAIEmbeddings and other SDKs don't use empty strings as base URLs
            for env_k in ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENROUTER_BASE_URL", "OPENROUTER_API_BASE", "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]:
                if env_k in os.environ and not os.environ[env_k].strip():
                    del os.environ[env_k]

            await websocket_event_emitter("logs", content="starting", output=f"🔍 Initializing research agent for: '{request.task}'")

            # Map tone and report types safely
            tone_map = {t.name.lower(): t for t in Tone}
            selected_tone = tone_map.get(request.tone.lower(), Tone.Objective)

            report_type_map = {r.name.lower(): r for r in ReportType}
            selected_report_type = report_type_map.get(request.report_type.lower(), ReportType.ResearchReport)

            report_source_map = {s.name.lower(): s for s in ReportSource}
            selected_source = report_source_map.get(request.report_source.lower(), ReportSource.Web)

            class WSProxy:
                def __init__(self, emitter):
                    self.emitter = emitter

                async def send_json(self, data: Any):
                    try:
                        if isinstance(data, dict):
                            # Ensure both content and output exist for Next.js parsing
                            if "type" not in data:
                                data["type"] = data.get("step", "logs")
                            if "content" not in data:
                                data["content"] = data.get("output", "")
                            if "output" not in data:
                                data["output"] = data.get("content", "")
                            await event_bus.publish(channel, data)
                        elif isinstance(data, list):
                            await self.emitter("logs", content="logs", output=str(data))
                        else:
                            await self.emitter("logs", content="logs", output=str(data))
                    except Exception as err:
                        logger.warning(f"WSProxy send_json warning: {err}")

            ws_proxy = WSProxy(websocket_event_emitter)

            # Instantiate researcher
            researcher = GPTResearcher(
                query=request.task,
                report_type=selected_report_type.value,
                report_source=selected_source.value,
                tone=selected_tone,
                websocket=ws_proxy
            )

            await websocket_event_emitter("logs", content="planning", output="📊 Generating research plan and sub-queries...")
            await researcher.conduct_research()

            await websocket_event_emitter("logs", content="writing", output="✍️ Synthesizing findings and drafting report...")
            report = await researcher.write_report()

            # Include sources & context
            sources = researcher.get_source_urls()
            costs = researcher.get_costs()

            # Export files via export-service
            paths = {}
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    for fmt in ["markdown", "pdf", "docx"]:
                        res = await client.post(f"{settings.EXPORT_URL}/export", json={
                            "report_markdown": report,
                            "title": request.task[:50],
                            "format": fmt
                        })
                        if res.status_code == 200:
                            data = res.json()
                            paths[fmt if fmt != "markdown" else "md"] = data.get("download_url")
            except Exception as exp_err:
                logger.warning(f"Auto-export error: {exp_err}")

            # Send final report to WebSocket
            await event_bus.publish(channel, {
                "type": "report",
                "content": "report",
                "output": report,
                "metadata": {"costs": costs, "sources_count": len(sources)}
            })

            # Send path event to notify frontend research is complete
            await event_bus.publish(channel, {
                "type": "path",
                "content": "path",
                "output": paths
            })

            await websocket_event_emitter("logs", content="done", output="✅ Research report successfully completed!")

            return {
                "session_id": session_id,
                "status": "completed",
                "report": report,
                "sources": sources,
                "costs": costs,
                "paths": paths
            }

        except Exception as e:
            logger.error(f"Error during research execution for {session_id}: {e}", exc_info=True)
            await websocket_event_emitter("error", content="error", output=f"Research failed: {str(e)}")
            return {
                "session_id": session_id,
                "status": "failed",
                "error": str(e)
            }

orchestrator = ResearchOrchestrator()
