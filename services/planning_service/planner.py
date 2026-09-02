import os
import sys
import json
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import PlanRequest, PlanResponse, SubtopicPlan
from gpt_researcher.utils.llm import create_chat_completion
from gpt_researcher.config import Config

logger = logging.getLogger("planning_service")

class ResearchPlanner:
    """Specialized agent service for planning research outlines and sub-queries."""

    async def generate_plan(self, request: PlanRequest) -> PlanResponse:
        logger.info(f"Generating research plan for task: '{request.task}' (Tone: {request.tone})")
        cfg = Config()

        child_run = None
        callbacks = []
        if request.parent_run_id and (os.getenv("LANGCHAIN_TRACING_V2") == "true" or os.getenv("LANGSMITH_TRACING") == "true"):
            try:
                from langsmith.run_trees import RunTree
                child_run = RunTree(
                    name="Planning Agent",
                    run_type="chain",
                    parent_run_id=request.parent_run_id,
                    inputs={"task": request.task, "tone": request.tone, "max_subtopics": request.max_subtopics},
                    project_name=os.getenv("LANGSMITH_PROJECT", "gpt-researcher")
                )
                child_run.post()
                callbacks = [child_run.get_langchain_callback()]
            except Exception as tr_err:
                logger.warning(f"Failed to create child RunTree for planner: {tr_err}")

        prompt = (
            f"You are a master research planner. Analyze the query and generate a focused plan with max {request.max_subtopics or 3} subtopics.\n\n"
            f"Research Query: \"{request.task}\"\n"
            f"Tone: {request.tone}\n\n"
            f"Provide a JSON response with the following format:\n"
            f"{{\n"
            f'  "outline": ["Introduction", "Subtopic 1", "Subtopic 2", "Conclusion"],\n'
            f'  "initial_summary": "High level summary",\n'
            f'  "subtopics": [\n'
            f'    {{\n'
            f'      "title": "Subtopic Title",\n'
            f'      "description": "Short focus",\n'
            f'      "subqueries": ["search query 1", "search query 2"]\n'
            f'    }}\n'
            f'  ]\n'
            f"}}\n"
            f"Output ONLY valid JSON."
        )

        messages = [
            {"role": "system", "content": "You are a research planner. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_response = await create_chat_completion(
                messages=messages,
                model=cfg.fast_llm_model,
                llm_provider=cfg.fast_llm_provider,
                temperature=0.3,
                max_tokens=600,
                callbacks=callbacks
            )

            # Strip markdown fences if present
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            subtopics = [
                SubtopicPlan(
                    title=st.get("title", ""),
                    description=st.get("description", ""),
                    subqueries=st.get("subqueries", [st.get("title", "")])
                )
                for st in parsed.get("subtopics", [])
            ]

            response = PlanResponse(
                task=request.task,
                outline=parsed.get("outline", [st.title for st in subtopics]),
                subtopics=subtopics,
                initial_summary=parsed.get("initial_summary", "")
            )

            if child_run:
                child_run.end(outputs=response.model_dump())
                child_run.patch()

            return response
        except Exception as e:
            logger.warning(f"Error parsing LLM plan: {e}. Falling back to default plan structure.")
            default_subtopic = SubtopicPlan(
                title=request.task,
                description="Comprehensive investigation",
                subqueries=[request.task, f"{request.task} overview", f"{request.task} analysis"]
            )
            fallback_res = PlanResponse(
                task=request.task,
                outline=["Introduction", request.task, "Analysis", "Conclusion"],
                subtopics=[default_subtopic],
                initial_summary="Direct investigation of research topic"
            )
            if child_run:
                child_run.end(outputs=fallback_res.model_dump())
                child_run.patch()
            return fallback_res

planner = ResearchPlanner()
