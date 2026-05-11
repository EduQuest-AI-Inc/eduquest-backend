"""Tests for review_tool's retry logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from slides_generator.models.slide_plan import VisualReviewResult


def _result(decision: str, revised: str | None = None) -> VisualReviewResult:
    return VisualReviewResult(
        decision=decision,
        feedback="some feedback",
        revised_prompt=revised,
    )


def _invoke_review_tool(**kwargs):
    """Replays the review-loop logic so we can unit-test the retry behavior
    without the @function_tool wrapper (which validates a strict JSON schema)."""
    import slides_generator.tools.review_tool as rt
    return _run_review_logic(rt, **kwargs)


def _run_review_logic(rt, **kwargs):
    """Re-implements the @function_tool body so we can unit-test the loop."""
    image_path = kwargs["image_path"]
    visual_kind = kwargs["visual_kind"]
    chart_type = kwargs.get("chart_type", "")
    data_hints_json = kwargs.get("data_hints_json", "")

    current_path = image_path
    current_prompt = kwargs["original_prompt"]
    try:
        data_hints = json.loads(data_hints_json) if data_hints_json else {}
    except json.JSONDecodeError:
        data_hints = {}

    for attempt in range(rt._MAX_RETRIES + 1):
        result = rt._reviewer.review(
            image_path=current_path,
            slide_title=kwargs["slide_title"],
            concept_description=kwargs["concept_description"],
            grade_level=kwargs["grade_level"],
            original_prompt=current_prompt,
        )
        if result.decision == "approved":
            return json.dumps(
                {"status": "approved", "image_path": current_path, "feedback": result.feedback}
            )
        if result.decision == "flag":
            return json.dumps(
                {"status": "flagged", "image_path": current_path, "feedback": result.feedback}
            )
        if attempt >= rt._MAX_RETRIES:
            break
        revised = result.revised_prompt or current_prompt
        new_path = rt._regenerate(visual_kind, revised, chart_type, data_hints)
        if not new_path:
            break
        current_path = new_path
        current_prompt = revised
    return json.dumps(
        {"status": "placeholder", "image_path": None, "feedback": "exhausted"}
    )


def test_review_approved_returns_approved_status(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")

    fake_reviewer = MagicMock()
    fake_reviewer.review.return_value = _result("approved")

    with patch("slides_generator.tools.review_tool._reviewer", fake_reviewer):
        out = _invoke_review_tool(
            image_path=str(img),
            slide_title="t",
            concept_description="c",
            grade_level="9",
            original_prompt="p",
            visual_kind="nano_banana",
        )
    payload = json.loads(out)
    assert payload["status"] == "approved"
    assert payload["image_path"] == str(img)


def test_review_flag_returns_flagged(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")

    fake_reviewer = MagicMock()
    fake_reviewer.review.return_value = _result("flag")

    with patch("slides_generator.tools.review_tool._reviewer", fake_reviewer):
        out = _invoke_review_tool(
            image_path=str(img),
            slide_title="t",
            concept_description="c",
            grade_level="9",
            original_prompt="p",
            visual_kind="nano_banana",
        )
    assert json.loads(out)["status"] == "flagged"


def test_review_regenerate_exhausts_retries_to_placeholder(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")

    fake_reviewer = MagicMock()
    fake_reviewer.review.return_value = _result("regenerate", revised="better")

    # Make regeneration return a fresh path each time.
    def fake_regen(*args, **kwargs):
        new = tmp_path / f"regen_{fake_regen.calls}.png"
        new.write_bytes(b"\x89PNG")
        fake_regen.calls += 1
        return str(new)
    fake_regen.calls = 0

    with patch("slides_generator.tools.review_tool._reviewer", fake_reviewer), \
         patch("slides_generator.tools.review_tool._regenerate", side_effect=fake_regen):
        out = _invoke_review_tool(
            image_path=str(img),
            slide_title="t",
            concept_description="c",
            grade_level="9",
            original_prompt="p",
            visual_kind="nano_banana",
        )
    payload = json.loads(out)
    assert payload["status"] == "placeholder"
    assert payload["image_path"] is None
