"""
review_tool — reviews a generated image with the Visual Review Agent and
absorbs the regenerate-retry loop internally so the orchestrator only has to
call this tool once per slide.

The orchestrator gets back a final decision: approved / flagged / placeholder
along with the (possibly-regenerated) image path.
"""

from __future__ import annotations

import json
import logging
import os

from agents import function_tool

from bots.slideshow.visual_review_agent import VisualReviewAgent
from models.slide_plan import ChartSpec
from integrations import nano_banana_client
from services.slides.visuals import chart_generator

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2

_reviewer = VisualReviewAgent()


def _regenerate(
    visual_kind: str,
    revised_prompt: str,
    chart_type: str,
    data_hints: dict,
) -> str | None:
    """Re-run the underlying visual generator with a revised prompt."""
    try:
        if visual_kind == "nano_banana":
            client = nano_banana_client.NanoBananaClient()
            return client.generate_image_to_file(revised_prompt)
        if visual_kind == "chart":
            spec = ChartSpec(
                chart_type=chart_type or "concept_map",
                description=revised_prompt,
                data_hints=data_hints or {},
            )
            return chart_generator.generate_chart_to_file(spec)
    except Exception as exc:  # noqa: BLE001
        logger.error("Regeneration failed (%s): %s", visual_kind, exc)
    return None


@function_tool
def review_visual(
    image_path: str,
    slide_title: str,
    concept_description: str,
    grade_level: str,
    original_prompt: str,
    visual_kind: str,
    chart_type: str = "",
    data_hints_json: str = "",
) -> str:
    """Review a generated image; auto-regenerates up to 2 times on fixable issues.

    ALWAYS call this immediately after `generate_nano_banana_image` or
    `generate_chart_image` - never place an unreviewed image on a slide.

    Args:
      image_path: Path returned by the upstream visual tool.
      slide_title: The slide's title (gives the reviewer context).
      concept_description: One-line summary of the concept being illustrated.
      grade_level: e.g. "9", "AP Biology", etc.
      original_prompt: The prompt that produced this image.
      visual_kind: "nano_banana" or "chart" - determines how to regenerate.
      chart_type: Required when visual_kind == "chart" (otherwise pass "").
      data_hints_json: JSON-encoded dict of chart data, required when
                       visual_kind == "chart" (otherwise pass "").

    Returns:
      JSON string: {
        "status": "approved" | "flagged" | "placeholder",
        "image_path": "<final image path or null>",
        "feedback": "<reviewer feedback>"
      }

      - approved   → use the image
      - flagged    → use the image but flag for human review (factual issue)
      - placeholder→ retries exhausted; render a styled placeholder instead

    Side effects: 1–3 vision API calls + up to 2 regenerations.
    Retry safety: NOT free — call once per slide.
    """
    current_path = image_path
    current_prompt = original_prompt

    try:
        data_hints = json.loads(data_hints_json) if data_hints_json else {}
    except json.JSONDecodeError:
        data_hints = {}

    for attempt in range(_MAX_RETRIES + 1):
        try:
            result = _reviewer.review(
                image_path=current_path,
                slide_title=slide_title,
                concept_description=concept_description,
                grade_level=grade_level,
                original_prompt=current_prompt,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Review agent error: %s", exc)
            return json.dumps(
                {"status": "flagged", "image_path": current_path, "feedback": str(exc)}
            )

        if result.decision == "approved":
            return json.dumps(
                {
                    "status": "approved",
                    "image_path": current_path,
                    "feedback": result.feedback,
                }
            )

        if result.decision == "flag":
            return json.dumps(
                {
                    "status": "flagged",
                    "image_path": current_path,
                    "feedback": result.feedback,
                }
            )

        # decision == "regenerate"
        if attempt >= _MAX_RETRIES:
            break

        revised = result.revised_prompt or current_prompt
        new_path = _regenerate(visual_kind, revised, chart_type, data_hints)
        if not new_path:
            break

        # Clean up the previous attempt's file
        if current_path and current_path != image_path and os.path.exists(current_path):
            try:
                os.unlink(current_path)
            except OSError:
                pass

        current_path = new_path
        current_prompt = revised

    return json.dumps(
        {
            "status": "placeholder",
            "image_path": None,
            "feedback": "Visual review exhausted retries; rendering placeholder.",
        }
    )
