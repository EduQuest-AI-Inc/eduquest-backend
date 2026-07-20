"""Teaching agent — generates modality-specific instructional content and retrieval prompts."""
from typing import Literal, Optional

from pydantic import BaseModel

from bots.model_config import TEACHING_AGENT_MODEL


class TeachingContent(BaseModel):
    modality: Literal["worked_example", "analogy"]
    content: str          # the instructional explanation
    retrieval_prompt: str  # the "now you try" practice question


_WORKED_EXAMPLE_INSTRUCTIONS = """\
You are an expert educational tutor delivering a worked example.

Given a skill, optional misconception context, and optionally an analogy the student has seen,
produce a clear worked example that:
1. Shows the skill in action with a concrete, step-by-step example
2. If a misconception is provided, explicitly corrects it before the example
3. Ends with a retrieval_prompt: a short practice question that requires the student to apply the same skill

Format: modality="worked_example", content=<the worked example>, retrieval_prompt=<the practice question>\
"""

_ANALOGY_INSTRUCTIONS = """\
You are an expert educational tutor explaining via analogy.

Given a skill, optional misconception context, and optionally a worked example the student has seen,
produce a clear analogy that:
1. Maps the skill to a familiar real-world scenario most students would recognize
2. If a misconception is provided, show why the analogy reveals the error in that thinking
3. Ends with a retrieval_prompt: a short question linking the analogy back to the actual skill

Format: modality="analogy", content=<the analogy explanation>, retrieval_prompt=<the practice question>\
"""


class TeachingAgent:
    """Generates instructional content in either worked_example or analogy modality."""

    def __init__(self, vector_store_ids: list[str] | None = None) -> None:
        from agents import Agent
        self._we_agent = Agent(
            name="WorkedExampleTeacher",
            instructions=_WORKED_EXAMPLE_INSTRUCTIONS,
            model=TEACHING_AGENT_MODEL,
            output_type=TeachingContent,
        )
        self._analogy_agent = Agent(
            name="AnalogyTeacher",
            instructions=_ANALOGY_INSTRUCTIONS,
            model=TEACHING_AGENT_MODEL,
            output_type=TeachingContent,
        )

    async def teach(
        self,
        skill_name: str,
        skill_description: str = "",
        modality: Literal["worked_example", "analogy"] = "worked_example",
        misconception_signature: Optional[str] = None,
        misconception_remediation: Optional[str] = None,
    ) -> TeachingContent:
        """Generate instructional content for a skill."""
        from agents import Runner
        from bots.tracing import build_trace_run_config

        parts = [f"Skill: {skill_name}"]
        if skill_description:
            parts.append(f"Description: {skill_description}")
        if misconception_signature:
            parts.append(f"Student misconception to address: {misconception_signature}")
        if misconception_remediation:
            parts.append(f"Suggested remediation approach: {misconception_remediation}")
        prompt = "\n".join(parts)

        agent = self._we_agent if modality == "worked_example" else self._analogy_agent
        result = await Runner.run(
            agent,
            prompt,
            run_config=build_trace_run_config(workflow_name=f"teaching_{modality}"),
        )
        return result.final_output
