"""Tests for the Orchestrator Agent (mocks Runner)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slides_generator.agents.orchestrator_agent import OrchestratorAgent
from slides_generator.models.slide_plan import CompletedSlide, CompleteSlideDeck

SAMPLE_LESSON = {
    "lesson_name": "Cellular Respiration",
    "concepts": [
        {
            "concept_name": "Glycolysis",
            "description": "Breakdown of glucose into pyruvate.",
            "prerequisites": ["ATP basics"],
            "common_misconceptions": ["Glycolysis happens in mitochondria"],
            "key_takeaways": ["Yields 2 ATP per glucose"],
            "skills": [
                {
                    "skill_name": "Trace glycolysis steps",
                    "description": "Identify each enzyme.",
                    "bloom_level": "Apply",
                    "difficulty": "intermediate",
                }
            ],
        }
    ],
}

SAMPLE_CONTEXT = {
    "period_name": "Biology 101",
    "grade_level": "9",
    "course_name": "Biology",
    "course_description": "Intro biology",
}


def _mock_deck() -> CompleteSlideDeck:
    return CompleteSlideDeck(
        lesson_name="Cellular Respiration",
        slides=[
            CompletedSlide(
                index=0,
                layout="title",
                title="Cellular Respiration",
                bullets=["Glycolysis", "Krebs Cycle", "ETC"],
                speaker_notes="Welcome students.",
            ),
            CompletedSlide(
                index=1,
                layout="concept_intro",
                title="Glycolysis",
                bullets=[
                    "Glucose → 2 pyruvate.",
                    "Occurs in cytoplasm",
                    "Yields 2 ATP",
                ],
                speaker_notes="Set the stage for the Krebs cycle.",
                prerequisites=["ATP basics"],
            ),
            CompletedSlide(
                index=2,
                layout="skill_card",
                title="Trace Glycolysis Steps",
                bullets=["Name 3 enzymes", "Identify reactants and products"],
                speaker_notes="Use the diagram to walk through each step.",
                bloom_level="Apply",
                difficulty="intermediate",
            ),
            CompletedSlide(
                index=3,
                layout="summary",
                title="Wrap Up",
                bullets=["Glycolysis happens in cytoplasm", "Yields 2 net ATP"],
                speaker_notes="Quick check for understanding.",
            ),
        ],
    )


@pytest.mark.asyncio
async def test_orchestrator_returns_complete_deck():
    mock_result = MagicMock()
    mock_result.final_output = _mock_deck()
    with patch("slides_generator.agents.orchestrator_agent.Runner") as mock_runner:
        mock_runner.run = AsyncMock(return_value=mock_result)
        deck = await OrchestratorAgent()._run_async(SAMPLE_LESSON, SAMPLE_CONTEXT)
    assert isinstance(deck, CompleteSlideDeck)
    assert len(deck.slides) == 4


def test_orchestrator_sync_run():
    mock_result = MagicMock()
    mock_result.final_output = _mock_deck()
    with patch("slides_generator.agents.orchestrator_agent.Runner") as mock_runner:
        mock_runner.run = AsyncMock(return_value=mock_result)
        deck = OrchestratorAgent().run(SAMPLE_LESSON, SAMPLE_CONTEXT)
    assert isinstance(deck, CompleteSlideDeck)


def test_deck_slides_have_required_fields():
    deck = _mock_deck()
    for slide in deck.slides:
        assert slide.title
        assert slide.bullets
        assert slide.speaker_notes
        assert slide.layout in {
            "title", "concept_intro", "two_col",
            "visual_focus", "skill_card", "summary",
        }


def test_skill_card_has_bloom_and_difficulty():
    deck = _mock_deck()
    skill_slides = [s for s in deck.slides if s.layout == "skill_card"]
    for s in skill_slides:
        assert s.bloom_level
        assert s.difficulty
