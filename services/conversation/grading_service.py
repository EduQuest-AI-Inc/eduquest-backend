"""
Grading service — wires the GradingOrchestrator into Flask.

Replaces the legacy ``update`` class from assistants.py for the student
submission / grading flow.  This is a one-shot orchestration (no
multi-turn conversation), so no OpenAIConversationsSession is needed.
"""
import asyncio
import json
from typing import Dict, Any, Optional

from bots.grading_agent import GradingInput, GradingResult
from bots.provider import get_bot_provider


def _read_submission_text(submission_path: str) -> str:
    """Read a submission file and return its text content."""
    try:
        with open(submission_path, "r", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[Unable to read submission file: {e}]"


def _build_grading_input(
    quest_data: Dict[str, Any],
    submission_text: str,
) -> GradingInput:
    """
    Adapt a quest dict (from IndividualQuestDAO) into the schema expected
    by ``GradingOrchestrator.grade_submission``.
    """
    rubric = quest_data.get("rubric", {})
    if isinstance(rubric, str):
        try:
            rubric = json.loads(rubric)
        except json.JSONDecodeError:
            rubric = {"raw": rubric}

    skills_raw = quest_data.get("skills", "")
    if isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(";") if s.strip()]
    elif isinstance(skills_raw, list):
        skills = skills_raw
    else:
        skills = []

    instructions = quest_data.get("instructions", quest_data.get("description", ""))

    return GradingInput(
        submission=submission_text,
        rubric=rubric,
        skills=skills,
        instructions=instructions,
    )


async def _grade(grading_input: GradingInput) -> GradingResult:
    orchestrator = get_bot_provider().create_grading_orchestrator()
    return await orchestrator.grade_submission(grading_input)


def grade_student_submission(
    quest_data: Dict[str, Any],
    submission_path: Optional[str] = None,
    submission_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synchronous entry-point called from ``ConversationService``.

    Accepts either a file path or raw text for the submission.

    Returns a plain dict compatible with the existing grade-persistence
    code in ``conversation_service.py``:
      - ``grade``          – ``{"detailed_grade": {criteria: score}, "overall_score": int}``
      - ``overall_score``  – int
      - ``feedback``       – str
      - ``change``         – bool
      - ``recommended_change`` – str | None
      - ``response``       – str (formatted for display)
    """
    if submission_text is None:
        if submission_path is None:
            raise ValueError("Either submission_path or submission_text is required")
        submission_text = _read_submission_text(submission_path)

    grading_input = _build_grading_input(quest_data, submission_text)
    result: GradingResult = asyncio.run(_grade(grading_input))

    recommended_change_text: Optional[str] = None
    if result.recommended_changes:
        recommended_change_text = "; ".join(result.recommended_changes)

    return {
        "grade": result.skill_mastery,
        "overall_score": result.numerical_grade,
        "feedback": result.feedback,
        "change": result.homework_changes_recommended,
        "recommended_change": recommended_change_text,
        "response": (
            f"Grade: {result.numerical_grade}\n"
            f"Feedback: {result.feedback}\n"
            f"Changes recommended: {result.homework_changes_recommended}"
        ),
    }
