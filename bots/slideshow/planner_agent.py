"""
Slide Planner Agent

Takes a lesson dict (matching the LessonSchema from the schedule agent) plus
period-level context and produces a SlidePlan: a structured list of SlideSpecs
with layouts, content hints, and visual requests.

The agent decides everything about the deck's structure — slide count, layout
per slide, and what visuals are needed — based on the lesson content and class
context. No fixed template is imposed.
"""

from __future__ import annotations

import asyncio
import json

from agents import Agent, FileSearchTool, Runner, WebSearchTool, trace
from dotenv import load_dotenv

from models.slide_plan import SlidePlan

load_dotenv()

_INSTRUCTIONS = """\
You are "Slide Architect," an AI agent that designs PowerPoint slide decks for teachers.

## Your job
Given a lesson (with its concepts and skills) and class context, produce a complete
SlidePlan: a structured list of slides with layouts, content hints, speaker notes, and
optional visual requests.

## Guiding principles
1. **Adapt to context.** The slide count and structure should match the complexity of the
   lesson. A lesson with 2 concepts may need 8 slides; one with 5 concepts may need 20.
2. **One idea per slide.** Never cram multiple concepts onto one slide.
3. **Rich and visual.** Prefer slides with supporting visuals over walls of text.
   Request a Nano Banana illustration when a concept benefits from an image (e.g. a diagram
   of a cell, a historical scene, a scientific process). Request a chart when something
   can be shown mathematically or as a process flow.
4. **Teacher-friendly speaker notes.** The speaker_notes_hints field should give the
   teacher concrete talking points, not just repeat the title.
5. **Bloom levels matter.** Skill slides should reflect the bloom_level — a "Remember"
   skill gets a definition-focused slide, an "Evaluate" skill gets a discussion prompt.

## Available layouts
- `title`        — Opening slide: lesson name, week, class info
- `concept_intro`— Concept name, description, prerequisites badge
- `two_col`      — Text/bullets on left, visual on right (good for most concept slides)
- `visual_focus` — Large image top, short caption below (use when the visual is central)
- `skill_card`   — Skill name, Bloom level badge, description, mastery criteria
- `summary`      — Recap all skills; what mastery looks like

## Visual types
- `nano_banana` — Request an AI-generated illustration via Google Gemini. Write a detailed,
                 specific prompt (e.g. "Cross-section diagram of a human muscle cell showing
                 cytoplasm, mitochondria, and ATP molecules, educational science illustration
                 style, clean white background, labeled").
- `chart`     — Request a Python-generated chart/diagram. Specify chart_type (bar, line,
                 equation_plot, process_flow, concept_map) and populate data_hints with
                 any relevant numbers, formulas, or labels from the lesson.
- `none`      — Text-only slide (title, skill_card, summary often need no visual).

## Output format
Return a valid SlidePlan JSON object. Every slide must have a unique zero-based index.
slide_count must equal the length of the slides array.
"""


class PlannerAgent:
    def __init__(self, vector_store_id: str) -> None:
        self.vector_store_id = vector_store_id
        self.agent = Agent(
            name="Slide Planner",
            instructions=_INSTRUCTIONS,
            model="gpt-5.5",
            tools=[
                FileSearchTool(
                    vector_store_ids=[self.vector_store_id]
                ),
                WebSearchTool()
            ],
            output_type=SlidePlan,
        )

    def _build_prompt(self, lesson: dict, period_context: dict) -> str:
        return f"""\
Please design a PowerPoint slide deck for the following lesson.

## Period / Class context
{json.dumps(period_context, indent=2)}

## Lesson data
{json.dumps(lesson, indent=2)}

Produce a SlidePlan that covers the entire lesson — title, each concept and its skills,
and a summary. Be generous with visuals; this is teaching material for a classroom.
"""

    async def _run_async(self, lesson: dict, period_context: dict) -> SlidePlan:
        prompt = self._build_prompt(lesson, period_context)
        with trace("slide_plan_generation"):
            result = await Runner.run(self.agent, prompt)
        return result.final_output

    def run(self, lesson: dict, period_context: dict) -> SlidePlan:
        return asyncio.run(self._run_async(lesson, period_context))
