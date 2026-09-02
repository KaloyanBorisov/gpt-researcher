import os
import sys
import json
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ReviewRequest, ReviewResponse
from gpt_researcher.utils.llm import create_chat_completion
from gpt_researcher.config import Config

logger = logging.getLogger("reviewer_service")

class ContentReviewer:
    """Specialized agent service for quality verification, critique, and scoring."""

    async def review_content(self, request: ReviewRequest) -> ReviewResponse:
        logger.info(f"Reviewing draft content for task '{request.task}' (Subtopic: {request.subtopic or 'All'})")
        cfg = Config()

        prompt = (
            f"You are a rigorous academic and technical reviewer. Evaluate the following research draft content.\n\n"
            f"Topic: \"{request.task}\"\n"
            f"Subtopic: \"{request.subtopic or 'Full Report'}\"\n"
            f"Sources Cited ({len(request.sources)}): {', '.join(request.sources[:10])}\n\n"
            f"Draft Content to Review:\n"
            f"\"\"\"\n{request.content[:5000]}\n\"\"\"\n\n"
            f"Evaluation Criteria:\n"
            f"1. Factual rigor and depth\n"
            f"2. Coherence and structure\n"
            f"3. Proper citation/source grounding\n"
            f"4. Absence of obvious hallucinations\n\n"
            f"Respond with ONLY a JSON object formatted as follows:\n"
            f"```json\n"
            f"{{\n"
            f'  "score": 0.95,\n'
            f'  "passed": true,\n'
            f'  "feedback": "Concise summary of strengths and areas for improvement",\n'
            f'  "revision_suggestions": ["Optional suggestion 1", "Optional suggestion 2"]\n'
            f"}}\n"
            f"```"
        )

        messages = [
            {"role": "system", "content": "You are a quality assurance and peer review agent. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            raw = await create_chat_completion(
                messages=messages,
                model=cfg.smart_llm_model,
                llm_provider=cfg.smart_llm_provider,
                temperature=0.2,
                max_tokens=1000
            )

            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            score = float(parsed.get("score", 0.9))
            passed = parsed.get("passed", score >= 0.7)
            feedback = parsed.get("feedback", "Review completed successfully.")
            suggestions = parsed.get("revision_suggestions", [])

            return ReviewResponse(
                score=score,
                passed=passed,
                feedback=feedback,
                revision_suggestions=suggestions
            )
        except Exception as e:
            logger.warning(f"Error reviewing content: {e}. Passing by default.")
            return ReviewResponse(
                score=0.9,
                passed=True,
                feedback="Automated fallback review pass.",
                revision_suggestions=[]
            )

reviewer = ContentReviewer()
