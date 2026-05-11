"""
Tests for the Visual Review Agent.
Mocks the OpenAI client so no real API calls are made.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from slides_generator.agents.visual_review_agent import VisualReviewAgent
from slides_generator.models.slide_plan import VisualReviewResult


def _write_dummy_png() -> str:
    """Write a minimal 1×1 white PNG and return its path."""
    # Minimal valid PNG bytes (1x1 transparent pixel)
    PNG_BYTES = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc"
        b"\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    fd, path = tempfile.mkstemp(suffix=".png")
    os.write(fd, PNG_BYTES)
    os.close(fd)
    return path


def _mock_response(decision: str, feedback: str, revised_prompt: str | None = None):
    payload = {"decision": decision, "feedback": feedback, "revised_prompt": revised_prompt}
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture()
def dummy_image():
    path = _write_dummy_png()
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_review_returns_approved(dummy_image):
    with patch("slides_generator.agents.visual_review_agent.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            "approved", "Image is clear and accurate."
        )
        mock_openai_cls.return_value = mock_client

        agent = VisualReviewAgent()
        result = agent.review(
            image_path=dummy_image,
            slide_title="Light Reactions",
            concept_description="How chloroplasts capture sunlight",
            grade_level="9",
            original_prompt="Diagram of chloroplast with labels",
        )

    assert isinstance(result, VisualReviewResult)
    assert result.decision == "approved"


def test_review_returns_regenerate(dummy_image):
    with patch("slides_generator.agents.visual_review_agent.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            "regenerate",
            "Labels are too small.",
            "Diagram of chloroplast with large readable labels, educational style",
        )
        mock_openai_cls.return_value = mock_client

        agent = VisualReviewAgent()
        result = agent.review(
            image_path=dummy_image,
            slide_title="Light Reactions",
            concept_description="How chloroplasts capture sunlight",
            grade_level="9",
            original_prompt="Diagram of chloroplast",
        )

    assert result.decision == "regenerate"
    assert result.revised_prompt is not None


def test_review_returns_flag(dummy_image):
    with patch("slides_generator.agents.visual_review_agent.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            "flag",
            "Image is completely unrelated to photosynthesis.",
        )
        mock_openai_cls.return_value = mock_client

        agent = VisualReviewAgent()
        result = agent.review(
            image_path=dummy_image,
            slide_title="Light Reactions",
            concept_description="How chloroplasts capture sunlight",
            grade_level="9",
            original_prompt="Diagram of chloroplast",
        )

    assert result.decision == "flag"


def test_review_handles_malformed_response(dummy_image):
    with patch("slides_generator.agents.visual_review_agent.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        msg = MagicMock()
        msg.content = "not valid json at all"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        mock_client.chat.completions.create.return_value = resp
        mock_openai_cls.return_value = mock_client

        agent = VisualReviewAgent()
        result = agent.review(
            image_path=dummy_image,
            slide_title="Test",
            concept_description="Test concept",
            grade_level="9",
            original_prompt="Test prompt",
        )

    # Should degrade gracefully to "flag" instead of raising
    assert result.decision == "flag"
