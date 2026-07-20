"""Misconception diagnosis agent — determines if a wrong answer stems from a known misconception."""
import json
from typing import Literal, Optional

from pydantic import BaseModel

from bots.model_config import MISCONCEPTION_AGENT_MODEL


class DiagnosisResult(BaseModel):
    failure_type: Literal["missing_skill", "misconception"]
    misconception_id: Optional[str] = None  # set only when a known misconception is matched


_INSTRUCTIONS = """\
You are an educational diagnostic specialist. Given:
- A skill being assessed
- A student's wrong answer
- A list of known misconceptions for this skill (with IDs, signatures, and remediation strategies)

Determine whether the student's error is:
1. A known MISCONCEPTION: their answer matches or strongly resembles one of the listed misconception patterns
2. MISSING_SKILL: the student simply doesn't know the material (no specific misconception pattern detected)

If the answer matches a known misconception, return its ID from the provided list.
If no match, return failure_type="missing_skill" and misconception_id=null.\
"""

_SCORER_INSTRUCTIONS_TEMPLATE = """\
Skill: {skill_name}
Student's wrong answer: {wrong_answer}

Known misconceptions for this skill:
{misconceptions_json}

Diagnose the failure type and return the misconception_id if matched.\
"""


class MisconceptionAgent:
    """Diagnoses whether a wrong answer matches a known misconception or indicates missing skill."""

    def __init__(self) -> None:
        from agents import Agent
        self._agent = Agent(
            name="MisconceptionDiagnoser",
            instructions=_INSTRUCTIONS,
            model=MISCONCEPTION_AGENT_MODEL,
            output_type=DiagnosisResult,
        )

    async def diagnose(
        self,
        skill_name: str,
        wrong_answer: str,
        known_misconceptions: list[dict],
    ) -> DiagnosisResult:
        """Diagnose a wrong answer against known misconceptions for a skill.

        known_misconceptions: list of misconception row dicts with misconception_id, signature.
        """
        from agents import Runner
        from bots.tracing import build_trace_run_config

        if not known_misconceptions:
            return DiagnosisResult(failure_type="missing_skill")

        misconceptions_json = json.dumps(
            [
                {
                    "misconception_id": m["misconception_id"],
                    "signature": m.get("signature", ""),
                }
                for m in known_misconceptions
            ],
            indent=2,
        )
        prompt = _SCORER_INSTRUCTIONS_TEMPLATE.format(
            skill_name=skill_name,
            wrong_answer=wrong_answer[:500],
            misconceptions_json=misconceptions_json,
        )
        result = await Runner.run(
            self._agent,
            prompt,
            run_config=build_trace_run_config(workflow_name="misconception_diagnosis"),
        )
        return result.final_output
