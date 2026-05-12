"""
Slide Generation Pipeline

Public entry point: `generate_slides(lesson, period_context) -> SlideOutput`.

The orchestrator agent now does most of the work — design, content writing,
visual generation, and visual review all happen inside its tool calls. This
module just glues the orchestrator's output to the three renderers.

Returns a `SlideOutput` containing:
  - html  (full standalone HTML, openable in any browser for preview)
  - pdf   (Playwright-rendered, primary download)
  - pptx  (python-pptx rendered, secondary editable export)
"""

from __future__ import annotations

import logging
import os

from agents import custom_span, trace

from bots.slideshow.orchestrator_agent import OrchestratorAgent
from models.slide_plan import (
    CompleteSlideDeck,
    SlideOutput,
)
from services.slides.renderer import pptx_renderer

logger = logging.getLogger(__name__)


def generate_slides(lesson: dict, period_context: dict) -> SlideOutput:
    """Generate HTML + PDF + PPTX outputs for one lesson.

    Args:
        lesson: A lesson dict matching the LessonSchema from the schedule
                agent (lesson_name, concepts, etc.).
        period_context: Dict with keys period_name, grade_level,
                        course_name, course_description, week_start
                        (optional), week_end (optional).

    Returns:
        SlideOutput(html, pdf, pptx).
    """
    trace_metadata = {
        "lesson_name": str(lesson.get("lesson_name", "")),
        "period_name": str(period_context.get("period_name", "")),
        "grade_level": str(period_context.get("grade_level", "")),
    }
    with trace("slides_pipeline", metadata=trace_metadata):
        logger.info("Running orchestrator for lesson: %s", lesson.get("lesson_name"))
        deck: CompleteSlideDeck = OrchestratorAgent().run(lesson, period_context)
        logger.info("Orchestrator complete: %d slides", len(deck.slides))

        html = deck.html_output or ""
        if not html:
            logger.warning("Orchestrator did not populate html_output; HTML will be empty")

        meta = {
            "lesson_name": lesson.get("lesson_name", deck.lesson_name),
            "period_name": period_context.get("period_name", ""),
            "grade_level": period_context.get("grade_level", ""),
            "week_start": period_context.get("week_start", ""),
            "week_end": period_context.get("week_end", ""),
        }

        # PDF rendering imports Playwright lazily — fall back gracefully if it's
        # not installed so HTML/PPTX still come back.
        try:
            from services.slides.renderer import pdf_renderer
            with custom_span("render_pdf"):
                pdf = pdf_renderer.render_pdf(html)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF rendering failed: %s", exc)
            pdf = b""

        with custom_span("render_pptx", data={"slide_count": len(deck.slides)}):
            pptx = pptx_renderer.render(deck.slides, meta=meta)

        _cleanup_temp_files(deck)

        return SlideOutput(html=html, pdf=pdf, pptx=pptx)


def _cleanup_temp_files(deck: CompleteSlideDeck) -> None:
    for cs in deck.slides:
        if cs.visual_path and os.path.exists(cs.visual_path):
            try:
                os.unlink(cs.visual_path)
            except OSError:
                pass
