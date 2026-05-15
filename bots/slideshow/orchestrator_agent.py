"""
Slide Orchestrator Agent

The orchestrator is a triage agent that designs the deck and calls specialist
sub-agents (content writer, chart generator, image generator, visual reviewer)
as `@function_tool` calls. It returns a fully-written `CompleteSlideDeck` with
all bullets, speaker notes, and approved image paths in place.

Replaces the older `PlannerAgent` (which only emitted a plan with hints).
"""

from __future__ import annotations

import json

from agents import Agent, ModelSettings, Runner, custom_span
from dotenv import load_dotenv

from models.slide_plan import CompleteSlideDeck
from bots.model_config import SLIDE_ORCHESTRATOR_MODEL
from bots.tools import SLIDE_TOOLS

load_dotenv()


_INSTRUCTIONS = """\
You are "Slide Orchestrator," an AI agent that designs and produces complete
PowerPoint decks for teachers. You have specialist tools for every step;
NEVER write slide copy yourself or place an unreviewed image on a slide.

## Your responsibilities
1. Design the deck: pick layouts, slide order, and slide count to match the
   lesson's complexity. Aim for one idea per slide; prefer visuals when a
   concept benefits from one.
2. For EVERY slide, call `write_slide_content(...)` to get final
   `title`, `bullets`, and `speaker_notes`. Pass the slide's layout, the
   concept context, key takeaways, common misconceptions, skills (as a
   JSON-encoded string in `skills_json`), and the grade level. Use the
   returned values verbatim.
3. For slides that need a visual:
   a. Call `generate_nano_banana_image(prompt)` for free-form illustrations
      (anatomy, historical scenes, photo-real imagery), OR
      `generate_chart_image(chart_type, description, data_hints_json)`
      for structured charts/diagrams. `data_hints_json` is a
      JSON-encoded dict - e.g. `'{"labels": ["A","B"], "values":[1,2]}'`.
   b. Immediately call `review_visual(...)` with the image path, slide
      title, concept description, grade level, and the original prompt
      (and `visual_kind` = "nano_banana" or "chart"; for chart also pass
      `chart_type` and `data_hints_json` so the reviewer can regenerate;
      pass empty strings for the nano_banana case).
   c. Use the returned `status` and `image_path` in the slide:
        - approved   → put the image on the slide (visual_status = "approved")
        - flagged    → keep the image but mark visual_status = "flagged"
        - placeholder→ no image; visual_status = "placeholder"
4. Build a `CompletedSlide` per slide with every required field populated.
5. Once ALL slides are written and visuals reviewed, call `render_html_deck(...)`
   as the FINAL tool call. Pass `lesson_name`, all completed slides serialized
   as a JSON array in `slides_json`, plus `period_name` and `grade_level`
   from the period context. Store the returned HTML string in `html_output`.

## Available layouts
- `title`         opening slide; bullets = agenda for the lesson
- `concept_intro` introduces a concept; one-sentence definition + facets
- `two_col`       bullets on the left, visual on the right (default workhorse)
- `visual_focus`  large central image with a one-sentence caption
- `skill_card`    one skill: bloom_level + difficulty badges + mastery bullets
- `summary`       recap of skills and what mastery looks like

## Layout-specific fields
- skill_card slides MUST set `bloom_level` and `difficulty`
- visual_focus slides MUST set `visual_caption` (also pass it as the only bullet)
- concept_intro slides MAY set `prerequisites` (list of prerequisite concept names)

## Deck structure
Always include:
  1 title slide
  per concept: concept_intro + (1–2 supporting two_col / visual_focus slides) + skill_card per skill
  1 summary slide

## Output
Return a `CompleteSlideDeck` with `lesson_name`, the ordered `slides`, and
`html_output` set to the string returned by `render_html_deck`.
Slide indices must be unique and zero-based. Every slide must have
non-empty `title`, `bullets`, and `speaker_notes`.
"""


class OrchestratorAgent:
    def __init__(self) -> None:
        self.agent = Agent(
            name="Slide Orchestrator",
            instructions=_INSTRUCTIONS,
            model=SLIDE_ORCHESTRATOR_MODEL,
            tools=SLIDE_TOOLS,
            output_type=CompleteSlideDeck,
            model_settings=ModelSettings(parallel_tool_calls=True),
        )

    def _build_prompt(self, lesson: dict, period_context: dict) -> str:
        return f"""\
Design and produce a complete PowerPoint deck for the lesson below.

## Period / class context
{json.dumps(period_context, indent=2)}

## Lesson data (concepts, skills, takeaways, misconceptions)
{json.dumps(lesson, indent=2)}

Use your tools for EVERY slide:
  - `write_slide_content` for the copy of every slide
  - `generate_nano_banana_image` or `generate_chart_image` when a visual helps
  - `review_visual` immediately after generating any visual

After ALL slides are written and visuals reviewed, call `render_html_deck`
as your FINAL tool call. Pass the full slides list as JSON in `slides_json`,
along with `period_name` and `grade_level` from the period context above.
Set `html_output` in the returned `CompleteSlideDeck` to the HTML string.
"""

    async def run_async(
        self, lesson: dict, period_context: dict
    ) -> CompleteSlideDeck:
        prompt = self._build_prompt(lesson, period_context)
        with custom_span("orchestrator"):
            result = await Runner.run(self.agent, prompt, max_turns=80)
        return result.final_output
