"""
html_tool — wraps the HTML renderer as a function tool.

The orchestrator calls this once as its final step, after all slides are
written and visuals reviewed. Returns the full standalone HTML document.
"""

from __future__ import annotations

import json

from agents import function_tool

from slides_generator.models.slide_plan import CompleteSlideDeck, CompletedSlide
from slides_generator.renderer import html_renderer


@function_tool
def render_html_deck(
    lesson_name: str,
    slides_json: str,
    period_name: str,
    grade_level: str,
    week_start: str = "",
    week_end: str = "",
) -> str:
    """Render the completed slide deck to a standalone HTML document.

    Call this LAST — after every slide has been written via `write_slide_content`
    and every visual has been reviewed via `review_visual`.

    Args:
      lesson_name: The lesson's name (echoed from the deck).
      slides_json: JSON-encoded list of CompletedSlide dicts (the full deck in order).
      period_name: Class / period name shown in the deck header.
      grade_level: e.g. "9", "AP Biology", "College freshman".
      week_start: Optional ISO date string for the week banner.
      week_end: Optional ISO date string for the week banner.

    Returns:
      Full standalone HTML document as a string.

    Side effects: one Jinja2 render — no API calls, safe to call once.
    """
    slides = [CompletedSlide.model_validate(s) for s in json.loads(slides_json)]
    deck = CompleteSlideDeck(lesson_name=lesson_name, slides=slides)
    meta = {
        "lesson_name": lesson_name,
        "period_name": period_name,
        "grade_level": grade_level,
        "week_start": week_start,
        "week_end": week_end,
    }
    return html_renderer.render_html(deck, meta)
