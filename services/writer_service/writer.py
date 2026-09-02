import os
import sys
import logging
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import SynthesisRequest, SynthesisResponse
from gpt_researcher.utils.llm import create_chat_completion
from gpt_researcher.config import Config

logger = logging.getLogger("writer_service")

class ReportWriter:
    """Specialized agent service for synthesizing structured section drafts into a comprehensive research report."""

    async def synthesize_report(self, request: SynthesisRequest) -> SynthesisResponse:
        logger.info(f"Synthesizing final research report for task: '{request.task}'")
        cfg = Config()

        # Assemble section drafts
        sections_text = ""
        for i, s in enumerate(request.sections, start=1):
            subtopic = s.get("subtopic", f"Section {i}")
            content = s.get("draft_content", "")
            sections_text += f"\n\n## {subtopic}\n{content}"

        sources_formatted = "\n".join([f"- {src}" for src in request.sources if src])

        prompt = (
            f"You are an expert research editor and synthesis author.\n"
            f"Task: \"{request.task}\"\n"
            f"Tone: {request.tone}\n\n"
            f"Here are the researched draft sections:\n"
            f"{sections_text}\n\n"
            f"Sources gathered:\n{sources_formatted}\n\n"
            f"Instructions:\n"
            f"1. Write a cohesive, comprehensive, high-quality Markdown research report starting with a # Title.\n"
            f"2. Add an Executive Summary at the beginning.\n"
            f"3. Integrate all section contents smoothly without redundant section duplication.\n"
            f"4. Add a Conclusion / Strategic Outlook section.\n"
            f"5. End with a ## References section listing all unique source links in markdown format.\n"
            f"Do not include meta-commentary, output ONLY the complete markdown report."
        )

        messages = [
            {"role": "system", "content": "You are a senior research editor. Write comprehensive, publication-ready research reports."},
            {"role": "user", "content": prompt}
        ]

        try:
            report_md = await create_chat_completion(
                messages=messages,
                model=cfg.smart_llm_model,
                llm_provider=cfg.smart_llm_provider,
                temperature=0.35,
                max_tokens=4000
            )
        except Exception as err:
            logger.error(f"Error during final report synthesis: {err}")
            # Fallback direct markdown assembly
            report_md = f"# {request.task}\n\n{sections_text}\n\n## References\n{sources_formatted}"

        word_count = len(report_md.split())
        return SynthesisResponse(
            report_markdown=report_md,
            total_words=word_count,
            sources_used=request.sources
        )

writer = ReportWriter()
