"""Artifact skill extractor — identifies academic skills evidenced in learner text."""
from pydantic import BaseModel, Field

from bots.model_config import ARTIFACT_EXTRACTOR_MODEL

_INSTRUCTIONS = """\
You are an educational skill extractor. Given redacted text from a learner's academic artifact \
(transcript, resume, essay, or other self-provided material), identify the specific academic skills \
and knowledge areas the learner has demonstrated evidence of.

For each skill:
- canonical_name: concise, specific skill name (e.g. "Quadratic equations", "Persuasive writing", \
"Python list comprehensions", "Cell mitosis")
- confidence: 0.0–1.0 indicating how strongly the artifact demonstrates this skill
  0.0 = mentioned in passing only; 0.5 = partial or indirect evidence; 1.0 = direct demonstration

Rules:
- Extract only skills with genuine evidence in the text. Do not infer unstated skills.
- Prefer specific skills (e.g. "Integration by parts") over vague ones (e.g. "Math").
- Output 0–20 skills; fewer is better than padded lists.
- Do not output PII — the text has already been redacted; placeholders like [NAME] are expected.\
"""


class ExtractedSkill(BaseModel):
    canonical_name: str
    confidence: float = Field(ge=0.0, le=1.0)


class ArtifactExtractionResult(BaseModel):
    skills: list[ExtractedSkill] = []


class ArtifactExtractor:
    """Extracts academic skills from redacted learner artifact text."""

    def __init__(self) -> None:
        from agents import Agent
        self._agent = Agent(
            name="ArtifactExtractor",
            instructions=_INSTRUCTIONS,
            model=ARTIFACT_EXTRACTOR_MODEL,
            output_type=ArtifactExtractionResult,
        )

    async def extract(self, text: str) -> ArtifactExtractionResult:
        from agents import Runner
        from bots.tracing import build_trace_run_config
        result = await Runner.run(
            self._agent,
            text[:4000],  # guard against very long artifacts
            run_config=build_trace_run_config(workflow_name="artifact_extraction"),
        )
        return result.final_output
