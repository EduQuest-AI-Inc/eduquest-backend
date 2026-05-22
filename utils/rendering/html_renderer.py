from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.slide_plan import CompleteSlideDeck

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "html.j2"]),
)


def _image_to_data_uri(path: str) -> str | None:
    try:
        file_path = Path(path)
        if not file_path.exists():
            return None
        mime_type, _ = mimetypes.guess_type(str(file_path))
        data = file_path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type or 'image/png'};base64,{encoded}"
    except OSError:
        return None


def render_html(deck: CompleteSlideDeck, meta: dict) -> str:
    """Render a CompleteSlideDeck to a standalone HTML string.

    Args:
        deck: A `CompleteSlideDeck` from the orchestrator.
        meta: Dict with optional keys lesson_name, period_name, grade_level,
              week_start, week_end. Used on the title slide.

    Returns:
        Standalone, self-contained HTML document with images embedded as base64.
    """
    image_data_uris: dict[int, str] = {}
    for slide in deck.slides:
        if slide.visual_path and slide.visual_status in ("approved", "flagged"):
            uri = _image_to_data_uri(slide.visual_path)
            if uri:
                image_data_uris[slide.index] = uri

    template = _env.get_template("base.html.j2")
    return template.render(deck=deck, meta=meta or {}, image_data_uris=image_data_uris)
