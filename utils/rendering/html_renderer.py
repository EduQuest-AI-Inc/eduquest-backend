from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.slide_plan import CompleteSlideDeck

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "html.j2"]),
)


def render_html(deck: CompleteSlideDeck, meta: dict) -> str:
    """Render a CompleteSlideDeck to a standalone HTML string.

    Args:
        deck: A `CompleteSlideDeck` from the orchestrator.
        meta: Dict with optional keys lesson_name, period_name, grade_level,
              week_start, week_end. Used on the title slide.

    Returns:
        Standalone HTML document.
    """
    template = _env.get_template("base.html.j2")
    return template.render(deck=deck, meta=meta or {})
