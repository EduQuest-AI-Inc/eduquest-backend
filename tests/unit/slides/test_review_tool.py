"""Tests for the visual review retry loop."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from models.slide_plan import VisualReviewResult
from utils.review_loop import run_review_loop

pytestmark = pytest.mark.unit


def _result(decision: str, revised: str | None = None) -> VisualReviewResult:
    return VisualReviewResult(
        decision=decision,
        feedback="some feedback",
        revised_prompt=revised,
    )


def _fake_reviewer(decision: str, revised: str | None = None) -> MagicMock:
    reviewer = MagicMock()
    reviewer.review.return_value = _result(decision, revised)
    return reviewer


def test_review_approved_returns_approved_status(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")

    out = run_review_loop(
        reviewer=_fake_reviewer("approved"),
        regenerate_fn=MagicMock(),
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

    out = run_review_loop(
        reviewer=_fake_reviewer("flag"),
        regenerate_fn=MagicMock(),
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

    call_count = 0

    def fake_regen(*args, **kwargs):
        nonlocal call_count
        new = tmp_path / f"regen_{call_count}.png"
        new.write_bytes(b"\x89PNG")
        call_count += 1
        return str(new)

    out = run_review_loop(
        reviewer=_fake_reviewer("regenerate", revised="better"),
        regenerate_fn=fake_regen,
        image_path=str(img),
        slide_title="t",
        concept_description="c",
        grade_level="9",
        original_prompt="p",
        visual_kind="nano_banana",
        max_retries=2,
    )
    payload = json.loads(out)
    assert payload["status"] == "placeholder"
    assert payload["image_path"] is None
