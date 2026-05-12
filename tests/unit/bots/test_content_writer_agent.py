"""Tests for ContentWriterAgent. Lives in unit/bots/ to use real_bots_imports fixture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

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


@pytest.mark.unit
def test_writer_returns_slide_content():
    from bots.slideshow.content_writer_agent import ContentWriterAgent
    from agents import Runner

    mock_result = MagicMock()
    mock_result.final_output = _mock_content()
    Runner.run = AsyncMock(return_value=mock_result)

    out = ContentWriterAgent().run(
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


@pytest.mark.unit
def test_writer_title_slide():
    from bots.slideshow.content_writer_agent import ContentWriterAgent
    from agents import Runner

    mock_result = MagicMock()
    mock_result.final_output = _mock_content()
    Runner.run = AsyncMock(return_value=mock_result)

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
