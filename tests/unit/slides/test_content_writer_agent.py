"""Tests for the Content Writer Agent (mocks Runner)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.slideshow.content_writer_agent import ContentWriterAgent
from models.slide_plan import SlideContent


def _mock_content() -> SlideContent:
    return SlideContent(
        title="Light Reactions",
        bullets=[
            "Chloroplasts capture light",
            "Water is split into oxygen",
            "ATP and NADPH are produced",
        ],
        speaker_notes="Walk students through the thylakoid membrane.",
    )


@pytest.mark.asyncio
async def test_writer_returns_slide_content():
    mock_result = MagicMock()
    mock_result.final_output = _mock_content()
    with patch("bots.content_writer_agent.Runner") as mock_runner:
        mock_runner.run = AsyncMock(return_value=mock_result)
        out = await ContentWriterAgent()._run_async(
            layout="concept_intro",
            title_hint="Light Reactions",
            concept_name="Light Reactions",
            concept_description="How chloroplasts capture sunlight.",
            key_takeaways=["ATP is produced"],
            common_misconceptions=["Plants eat sunlight"],
            skills=[],
            grade_level="9",
            course_context="Biology",
        )
    assert isinstance(out, SlideContent)
    assert out.title == "Light Reactions"
    assert len(out.bullets) == 3
    assert out.speaker_notes


def test_writer_sync_run():
    mock_result = MagicMock()
    mock_result.final_output = _mock_content()
    with patch("bots.content_writer_agent.Runner") as mock_runner:
        mock_runner.run = AsyncMock(return_value=mock_result)
        out = ContentWriterAgent().run(
            layout="title",
            title_hint="Welcome",
            concept_name="",
            concept_description="",
            key_takeaways=[],
            common_misconceptions=[],
            skills=[],
            grade_level="9",
            course_context="Biology",
        )
    assert isinstance(out, SlideContent)
