from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class VisualType(str, Enum):
    NANO_BANANA = "nano_banana"
    CHART = "chart"
    NONE = "none"


class ChartSpec(BaseModel):
    chart_type: str = Field(
        description=(
            "One of: bar, line, equation_plot, process_flow, concept_map, scatter, pie"
        )
    )
    description: str = Field(description="Plain-English description of what to show")
    data_hints: dict = Field(
        default_factory=dict,
        description=(
            "Numerical data, formulas, or labels the chart should use. "
            "e.g. {'x_label': 'Time (s)', 'y_label': 'Velocity', 'formula': 'v = u + at'}"
        ),
    )


class VisualRequest(BaseModel):
    visual_type: VisualType
    prompt: str = Field(
        description=(
            "For NANO_BANANA: the image generation prompt. "
            "For CHART: a short human-readable label (use chart_spec for details)."
        )
    )
    chart_spec: Optional[ChartSpec] = Field(
        default=None, description="Populated only when visual_type is CHART"
    )


class SlideSpec(BaseModel):
    index: int = Field(description="Zero-based slide index")
    layout: str = Field(
        description=(
            "One of: title | concept_intro | two_col | visual_focus | skill_card | summary"
        )
    )
    title: str
    content_hints: List[str] = Field(
        description="Bullet points or key ideas the slide should convey"
    )
    speaker_notes_hints: str = Field(
        description="Guidance for speaker notes — talking points for the teacher"
    )
    visual_request: Optional[VisualRequest] = None


class SlidePlan(BaseModel):
    lesson_name: str
    slide_count: int
    slides: List[SlideSpec]


class VisualReviewResult(BaseModel):
    decision: Literal["approved", "regenerate", "flag"] = Field(
        description=(
            "'approved' = image is good; "
            "'regenerate' = image has issues, revised_prompt provided; "
            "'flag' = serious problem requiring human review"
        )
    )
    feedback: str = Field(description="Explanation of the decision")
    revised_prompt: Optional[str] = Field(
        default=None,
        description="Improved Nano Banana/chart prompt to use on regeneration attempt",
    )


class GeneratedSlide(BaseModel):
    spec: SlideSpec
    visual_path: Optional[str] = Field(
        default=None, description="Absolute path to approved image temp file"
    )
    visual_status: Literal["approved", "flagged", "placeholder", "none"] = "none"


# ─────────────────────────────────────────────────────────────────────────────
# New orchestrator-era models
# ─────────────────────────────────────────────────────────────────────────────


class SlideContent(BaseModel):
    """Output of the Content Writer Agent — final written copy for one slide."""

    title: str
    bullets: List[str] = Field(
        default_factory=list,
        description="Final written bullets — short phrases, not full paragraphs",
    )
    speaker_notes: str = Field(
        description="Final speaker notes the teacher will read"
    )


class CompletedSlide(BaseModel):
    """A fully-written slide ready for rendering (HTML / PDF / PPTX)."""

    index: int = Field(description="Zero-based slide index")
    layout: Literal[
        "title", "concept_intro", "two_col", "visual_focus", "skill_card", "summary"
    ]
    title: str
    bullets: List[str] = Field(default_factory=list)
    speaker_notes: str = ""
    visual_path: Optional[str] = Field(
        default=None, description="Absolute path to approved image temp file"
    )
    visual_status: Literal["approved", "flagged", "placeholder", "none"] = "none"
    visual_caption: Optional[str] = Field(
        default=None, description="Caption text for visual_focus layout"
    )
    bloom_level: Optional[str] = Field(
        default=None, description="For skill_card Bloom badge"
    )
    difficulty: Optional[str] = Field(
        default=None, description="For skill_card difficulty badge"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="For concept_intro prerequisite chips",
    )


class CompleteSlideDeck(BaseModel):
    """The orchestrator's final structured output."""

    lesson_name: str
    slides: List[CompletedSlide]
    html_output: Optional[str] = Field(
        default=None,
        description="Rendered HTML document — populated by the render_html_deck tool call",
    )


@dataclass
class SlideOutput:
    """Triple-format result from `pipeline.generate_slides`."""

    html: str
    pdf: bytes
    pptx: bytes
