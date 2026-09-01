import os
import sys
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import SynthesisRequest, SynthesisResponse
from gpt_researcher.utils.llm import create_chat_completion
from gpt_researcher.config import Config

logger = logging.getLogger("writer_service")

class ReportWriter:
    """Specialized agent service for synthesizing researched sections into publication-ready reports."""

    async def synthesize_report(self, request: SynthesisRequest) -> SynthesisResponse:
        logger.info(f"Synthesizing report for task '{request.task}' with {len(request.sections)} sections")
        cfg = Config()

        # Compile body content from sections
        section_texts = []
        all_sources: List[str] = list(request.sources)
        for s in request.sections:
            title = s.get("subtopic", "Section")
            draft = s.get("draft_content", "")
            sources = s.get("sources", [])
            for src in sources:
                if src and src not in all_sources:
                    all_sources.append(src)
            section_texts.append(f"## {title}\n\n{draft}")

        combined_body = "\n\n".join(section_texts)

        prompt = (
            f"You are a chief technical writer and editor. Synthesize the following section drafts into a polished, "
            f"coherent, and publication-ready research report.\n\n"
            f"Report Title / Task: \"{request.task}\"\n"
            f"Tone: {request.tone}\n"
            f"Report Type: {request.report_type}\n\n"
            f"Drafted Section Content:\n"
            f"{combined_body[:10000]}\n\n"
            f"Instructions:\n"
            f"1. Write a compelling `# {request.task}` main title and Executive Summary / Introduction.\n"
            f"2. Integrate the section drafts smoothly with clean transitions, headings (`##`, `###`), and markdown tables if relevant.\n"
            f"3. Write a thorough Conclusion and Key Takeaways section.\n"
            f"4. Add a `## References` section at the end listing the cited sources.\n"
            f"Do not include meta-commentary, output only the clean markdown report."
        )

        messages = [
            {"role": "system", "content": "You are a master technical writer synthesizing a comprehensive report."},
            {"role": "user", "content": prompt}
        ]

        try:
            final_report = await create_chat_completion(
                messages=messages,
                model=cfg.smart_llm_model,
                llm_provider=cfg.smart_llm_provider,
                temperature=0.35,
                max_tokens=4500
            )
        except Exception as e:
            logger.error(f"Error synthesizing report with LLM: {e}. Falling back to assembled sections.")
            final_report = f"# {request.task}\n\n{combined_body}\n\n## References\n\n" + "\n".join([f"- {src}" for src in all_sources[:15]])

        word_count = len(final_report.split())

        return SynthesisResponse(
            report_markdown=final_report,
            total_words=word_count,
            sources_used=all_sources
        )

writer = ReportWriter()
