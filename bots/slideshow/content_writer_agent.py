"""
Content Writer Agent

A single-purpose agent invoked by the orchestrator (via `content_tool.py`) to
produce the final, written copy for one slide. It does NOT decide layout or
visuals — only the title, bullets, and speaker notes.

Pattern follows `bots/schedule_agent.py` — `Agent` with structured `output_type`.
"""

from __future__ import annotations

import asyncio
import json

from agents import Agent, Runner
from dotenv import load_dotenv

from models.slide_plan import SlideContent
from bots.model_config import SLIDE_CONTENT_WRITER_MODEL

load_dotenv()


_INSTRUCTIONS = """\
You are "Slide Copywriter," an expert at producing tight, classroom-ready slide
copy for K–12 and college teachers.

You receive ONE slide's worth of context (layout, concept info, skills, grade
level) and must return final written copy for that slide:

  - **title**: 3–8 word slide title. No trailing punctuation. Use Title Case.
  - **bullets**: 3–5 short phrases (≤ 12 words each). No nested bullets, no full
    sentences. For `title` and `summary` layouts the bullets become the agenda /
    recap items. For `skill_card` they should describe what mastery looks like.
  - **speaker_notes**: 2–4 sentences of teacher-facing talking points.
    Concrete examples, anticipated student questions, common misconceptions —
    NOT a re-statement of the bullets.

## Layout-specific guidance
- `title` — bullets = "what we'll cover today" agenda items.
- `concept_intro` — bullets = key facets of the concept; first bullet should be
  a one-line definition.
- `two_col` — bullets = main teaching points; speaker_notes should reference the
  visual (it sits to the right).
- `visual_focus` — exactly ONE bullet, used as caption for the central image.
- `skill_card` — bullets describe observable mastery behaviors ("Student can…").
- `summary` — bullets recap the lesson's skills and what mastery looks like.

## Tone
- Calibrate vocabulary to the grade level you're given.
- Active voice. No filler ("In this lesson we will…"). No emojis.
- Never start a bullet with the same word as the title.
"""


class ContentWriterAgent:
    def __init__(self) -> None:
        self.agent = Agent(
            name="Slide Copywriter",
            instructions=_INSTRUCTIONS,
            model=SLIDE_CONTENT_WRITER_MODEL,
            output_type=SlideContent,
        )

    def _build_prompt(
        self,
        layout: str,
        title_hint: str,
        concept_name: str,
        concept_description: str,
        key_takeaways: list[str],
        common_misconceptions: list[str],
        skills: list[dict],
        grade_level: str,
        course_context: str,
    ) -> str:
        return f"""\
Write the final copy for one slide.

## Slide context
- layout: {layout}
- title_hint: {title_hint}
- grade_level: {grade_level}
- course_context: {course_context}

## Concept being taught
- name: {concept_name}
- description: {concept_description}
- key_takeaways: {json.dumps(key_takeaways, indent=2)}
- common_misconceptions: {json.dumps(common_misconceptions, indent=2)}
- skills: {json.dumps(skills, indent=2)}

Return a SlideContent object with `title`, `bullets`, and `speaker_notes`.
"""

    async def _run_async(self, **kwargs) -> SlideContent:
        prompt = self._build_prompt(**kwargs)
        result = await Runner.run(self.agent, prompt)
        return result.final_output

    async def run_async(self, **kwargs) -> SlideContent:
        return await self._run_async(**kwargs)

    def run(self, **kwargs) -> SlideContent:
        return asyncio.run(self._run_async(**kwargs))
