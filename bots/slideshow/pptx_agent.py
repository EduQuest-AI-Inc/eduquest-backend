"""
PptxAgent — generates a PowerPoint deck for one lesson.

Drives the full multi-agent pipeline (orchestrator → content writer → visual
review) and renders the result to PPTX bytes. PDF/HTML are produced as
by-products but only PPTX bytes are returned; S3 upload happens in the
service layer.
"""

from __future__ import annotations

import logging
import os

from agents import custom_span, trace

from bots.slideshow.orchestrator_agent import OrchestratorAgent
from utils.rendering import html_renderer, pptx_renderer

logger = logging.getLogger(__name__)


class PptxAgent:
    async def run(self, lesson: dict, period_context: dict) -> dict:
        """Generate a PPTX and HTML for one lesson.

        Returns:
            Dict with ``pptx_bytes`` (bytes) and ``html_str`` (str).
        """
        trace_metadata = {
            "lesson_name": str(lesson.get("lesson_name", "")),
            "period_name": str(period_context.get("period_name", "")),
            "grade_level": str(period_context.get("grade_level", "")),
        }
        with trace("pptx_agent", metadata=trace_metadata):
            logger.info("Running orchestrator for lesson: %s", lesson.get("lesson_name"))
            deck = await OrchestratorAgent().run_async(lesson, period_context)
            logger.info("Orchestrator complete: %d slides", len(deck.slides))

            meta = {
                "lesson_name": lesson.get("lesson_name", deck.lesson_name),
                "period_name": period_context.get("period_name", ""),
                "grade_level": period_context.get("grade_level", ""),
                "week_start": period_context.get("week_start", ""),
                "week_end": period_context.get("week_end", ""),
            }

            with custom_span("render_pptx", data={"slide_count": len(deck.slides)}):
                pptx_bytes = pptx_renderer.render(deck.slides, meta=meta)
                html_str = html_renderer.render_html(deck, meta)

            _cleanup_temp_files(deck)

        return {"pptx_bytes": pptx_bytes, "html_str": html_str}


def _cleanup_temp_files(deck) -> None:
    for cs in deck.slides:
        if cs.visual_path and os.path.exists(cs.visual_path):
            try:
                os.unlink(cs.visual_path)
            except OSError:
                pass
