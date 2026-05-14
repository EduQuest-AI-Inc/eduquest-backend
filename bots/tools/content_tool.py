"""
content_tool — wraps the Content Writer Agent as a function tool.

The orchestrator calls this once per slide to get final title, bullets, and
speaker notes. The tool returns a JSON string (rather than a Pydantic model)
because the SDK serializes tool results back into the model's context as text.
"""

from __future__ import annotations

import asyncio
import json

from agents import function_tool

from bots.slideshow.content_writer_agent import ContentWriterAgent

_CONTENT_TIMEOUT_S = 60

# Single shared writer instance — agent objects are stateless / reusable.
_writer = ContentWriterAgent()


@function_tool
async def write_slide_content(
    layout: str,
    title_hint: str,
    concept_name: str,
    concept_description: str,
    key_takeaways: list[str],
    common_misconceptions: list[str],
    skills_json: str,
    grade_level: str,
    course_context: str,
) -> str:
    """Write the final title, bullets, and speaker notes for one slide.

    Use this for EVERY slide — never invent slide copy yourself.

    Args:
      layout: One of `title | concept_intro | two_col | visual_focus | skill_card | summary`.
      title_hint: A working title (you may improve on it).
      concept_name: The concept being taught on this slide.
      concept_description: One-paragraph description of the concept.
      key_takeaways: Bullet-form key points from the lesson plan.
      common_misconceptions: Things students typically get wrong.
      skills_json: JSON-encoded list of skill dicts (name, bloom_level,
                   difficulty, description).
      grade_level: e.g. "9", "AP Biology", "College freshman".
      course_context: e.g. "AP Biology, Unit 3 — Cellular Energetics".

    Returns:
      JSON string with keys `title`, `bullets`, `speaker_notes`.

    Side effects: makes one OpenAI API call.
    Retry safety: idempotent — safe to retry on transient errors.
    """
    try:
        skills = json.loads(skills_json) if skills_json else []
    except json.JSONDecodeError:
        skills = []
    try:
        content = await asyncio.wait_for(
            _writer.run_async(
                layout=layout,
                title_hint=title_hint,
                concept_name=concept_name,
                concept_description=concept_description,
                key_takeaways=key_takeaways,
                common_misconceptions=common_misconceptions,
                skills=skills,
                grade_level=grade_level,
                course_context=course_context,
            ),
            timeout=_CONTENT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Slide content generation timed out after {_CONTENT_TIMEOUT_S} s"
        )
    return json.dumps(content.model_dump())
