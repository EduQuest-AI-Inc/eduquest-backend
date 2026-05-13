"""
Visual Review Agent

Uses GPT-4o vision to review generated images (from Nano Banana or the chart
generator) before they are placed on slides. Returns an approval decision,
feedback, and - when the image should be regenerated - an improved prompt.

Uses the raw OpenAI client directly (not the openai-agents SDK) because we
need to pass base64 image content in the message, which is simpler with the
client directly.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from agents import custom_span
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from models.slide_plan import VisualReviewResult

load_dotenv()

_SYSTEM_PROMPT = """\
You are an expert educational content reviewer. You evaluate images that will
appear on teacher-facing PowerPoint slides. You check three things:

1. **Factual accuracy** — Does the image correctly represent the concept or skill?
2. **Clarity** — Is the diagram/illustration clear and readable when projected at
   classroom scale? Labels should be legible, layouts uncluttered.
3. **Audience appropriateness** — Is the style and complexity suitable for the
   stated grade level?

Return a JSON object with exactly these fields:
{
  "decision": "approved" | "regenerate" | "flag",
  "feedback": "<explanation>",
  "revised_prompt": "<improved prompt>" | null
}

Use "approved" if the image is good to use.
Use "regenerate" if it has fixable issues — provide a revised_prompt with specific
  improvements (e.g. "add labels", "use cleaner layout", "show the cytoplasm only").
Use "flag" only for serious problems: factually wrong in a way that would mislead
  students, or completely irrelevant to the concept.
"""


class VisualReviewAgent:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def review(
        self,
        image_path: str,
        slide_title: str,
        concept_description: str,
        grade_level: str,
        original_prompt: str,
    ) -> VisualReviewResult:
        """
        Review a generated image and return an approval decision.

        Args:
            image_path: Absolute path to the PNG image file.
            slide_title: Title of the slide this image belongs to.
            concept_description: Description of the concept being illustrated.
            grade_level: e.g. "9", "AP", "College"
            original_prompt: The Nano Banana/chart prompt that produced this image.
        """
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()

        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"**Slide title:** {slide_title}\n"
                        f"**Concept:** {concept_description}\n"
                        f"**Grade level:** {grade_level}\n"
                        f"**Original prompt used to generate this image:**\n{original_prompt}\n\n"
                        "Please review the image below and return your decision as JSON."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                },
            ],
        }

        span_data: dict[str, str] = {
            "slide_title": slide_title,
            "grade_level": grade_level,
            "model": "gpt-5.5",
        }
        with custom_span("visual_review", data=span_data):
            response = self._client.chat.completions.create(
                model="gpt-5.5",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    user_message,
                ],
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or "{}"
            try:
                import json
                result = VisualReviewResult.model_validate(json.loads(raw))
                span_data["decision"] = result.decision
                return result
            except (ValidationError, ValueError) as exc:
                span_data["decision"] = "flag"
                span_data["error"] = str(exc)
                return VisualReviewResult(
                    decision="flag",
                    feedback=f"Review agent returned unparseable response: {exc}",
                    revised_prompt=None,
                )
