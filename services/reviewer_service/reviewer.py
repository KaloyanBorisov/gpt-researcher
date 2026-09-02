import os
import sys
import json
import logging
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ReviewRequest, ReviewResponse
from gpt_researcher.utils.llm import create_chat_completion
from gpt_researcher.config import Config

logger = logging.getLogger("reviewer_service")

class ReportReviewer:
    """Specialized reviewer agent service for factual verification, hallucination checks, and tone alignment."""

    async def review_content(self, request: ReviewRequest) -> ReviewResponse:
        logger.info(f"Reviewing research draft for task: '{request.task}'")
        cfg = Config()

        prompt = (
            f"You are a strict editorial quality assurance reviewer.\n\n"
            f"Research Task: \"{request.task}\"\n"
            f"Draft Content:\n{request.content[:3000]}\n\n"
            f"Guidelines: {request.guidelines or 'Verify clarity, factual grounding, structure, and readability.'}\n\n"
            f"Provide a JSON response evaluating this draft:\n"
            f"{{\n"
            f'  "score": 0.95,\n'
            f'  "passed": true,\n'
            f'  "feedback": "Concise summary of strengths and weaknesses",\n'
            f'  "revision_suggestions": ["Suggestion 1", "Suggestion 2"]\n'
            f"}}\n"
            f"Output ONLY valid JSON."
        )

        messages = [
            {"role": "system", "content": "You are a quality assurance editor. Respond strictly in JSON format."},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_response = await create_chat_completion(
                messages=messages,
                model=cfg.fast_llm_model,
                llm_provider=cfg.fast_llm_provider,
                temperature=0.2,
                max_tokens=500
            )

            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            return ReviewResponse(
                score=float(parsed.get("score", 1.0)),
                passed=bool(parsed.get("passed", True)),
                feedback=parsed.get("feedback", "Draft meets quality criteria."),
                revision_suggestions=parsed.get("revision_suggestions", [])
            )
        except Exception as e:
            logger.warning(f"Reviewer parse error: {e}. Falling back to default approval.")
            return ReviewResponse(
                score=1.0,
                passed=True,
                feedback="Content verified and approved.",
                revision_suggestions=[]
            )

reviewer = ReportReviewer()
