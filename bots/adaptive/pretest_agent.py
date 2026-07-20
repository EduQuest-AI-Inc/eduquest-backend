"""Adaptive pretest agents — item generation and scoring."""
from typing import Literal

from pydantic import BaseModel

from bots.model_config import PRETEST_ITEM_MODEL, PRETEST_SCORER_MODEL

_ITEM_INSTRUCTIONS = """\
You are an educational assessment designer. Given a skill name and optional description, \
generate a single clear assessment question that tests whether a student knows this skill.

Requirements:
- One question only; no preamble or explanation
- Open-ended (not multiple choice) — the student writes their answer in 1-3 sentences
- Specific enough that a knowledgeable student can answer in 1-3 sentences
- Appropriate for a student who may or may not have studied this topic recently
- Include the skill_name field exactly as provided\
"""

_SCORER_INSTRUCTIONS = """\
You are an educational scorer. Given a skill being assessed, the question asked, \
and a student's free-text answer, score the answer.

Scoring rules:
- correct: answer demonstrates clear understanding of the skill
- partial: answer shows some relevant knowledge but is incomplete or has minor errors
- incorrect: answer is wrong, off-topic, or shows no understanding

Provide a short rationale (1-2 sentences) explaining the score.\
"""


class PretestItemSchema(BaseModel):
    prompt: str
    skill_name: str


class PretestScoringResult(BaseModel):
    result: Literal["correct", "incorrect", "partial"]
    rationale: str


class PretestAgent:
    """Two-agent pretest pipeline: generate items and score learner answers."""

    def __init__(self, vector_store_ids: list[str] | None = None) -> None:
        from agents import Agent
        self._item_agent = Agent(
            name="PretestItemGenerator",
            instructions=_ITEM_INSTRUCTIONS,
            model=PRETEST_ITEM_MODEL,
            output_type=PretestItemSchema,
        )
        self._scorer_agent = Agent(
            name="PretestScorer",
            instructions=_SCORER_INSTRUCTIONS,
            model=PRETEST_SCORER_MODEL,
            output_type=PretestScoringResult,
        )

    async def generate_item(self, skill_name: str, description: str = "") -> PretestItemSchema:
        """Generate one assessment question for the given skill."""
        from agents import Runner
        from bots.tracing import build_trace_run_config
        prompt = f"Skill: {skill_name}"
        if description:
            prompt += f"\nDescription: {description}"
        result = await Runner.run(
            self._item_agent,
            prompt,
            run_config=build_trace_run_config(workflow_name="pretest_item_generation"),
        )
        return result.final_output

    async def score_answer(
        self,
        skill_name: str,
        item_prompt: str,
        learner_answer: str,
    ) -> PretestScoringResult:
        """Score a learner's answer to a pretest item."""
        from agents import Runner
        from bots.tracing import build_trace_run_config
        scoring_input = (
            f"Skill being assessed: {skill_name}\n"
            f"Question: {item_prompt}\n"
            f"Student answer: {learner_answer}"
        )
        result = await Runner.run(
            self._scorer_agent,
            scoring_input,
            run_config=build_trace_run_config(workflow_name="pretest_scoring"),
        )
        return result.final_output
