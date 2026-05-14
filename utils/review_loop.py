"""
Pure retry-loop logic for visual review.

Extracted from bots/tools/review_tool.py so it can be tested without the
@function_tool decorator or any bots/ module stubs.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)


def run_review_loop(
    reviewer,
    regenerate_fn: Callable,
    image_path: str,
    slide_title: str,
    concept_description: str,
    grade_level: str,
    original_prompt: str,
    visual_kind: str,
    chart_type: str = "",
    data_hints_json: str = "",
    max_retries: int = 2,
) -> str:
    """Run the visual review retry loop and return a JSON status string.

    Returns JSON: {"status": "approved"|"flagged"|"placeholder", "image_path": ..., "feedback": ...}
    """
    current_path = image_path
    current_prompt = original_prompt

    try:
        data_hints = json.loads(data_hints_json) if data_hints_json else {}
    except json.JSONDecodeError:
        data_hints = {}

    for attempt in range(max_retries + 1):
        try:
            result = reviewer.review(
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
        if attempt >= max_retries:
            break

        revised = result.revised_prompt or current_prompt
        new_path = regenerate_fn(visual_kind, revised, chart_type, data_hints)
        if not new_path:
            break

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
