"""
Grading service — wires the GradingOrchestrator into Flask.

Replaces the legacy ``update`` class from assistants.py for the student
submission / grading flow.  This is a one-shot orchestration (no
multi-turn conversation), so no OpenAIConversationsSession is needed.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from bots import GradingInput, GradingResult
from bots.provider import get_bot_provider

logger = logging.getLogger(__name__)


def _read_submission_text(submission_path: str) -> str:
    if submission_path.lower().endswith(".pdf"):
        return _extract_pdf_text(submission_path)
    try:
        with open(submission_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[Unable to read submission file: {e}]"


def _extract_pdf_text(path: str) -> str:
    try:
        reader = PdfReader(path)
    except PdfReadError as e:
        return f"[Corrupted or invalid PDF — unable to parse: {e}]"
    except Exception as e:
        return f"[Unable to open PDF: {e}]"

    if reader.is_encrypted:
        return "[PDF is password-protected and cannot be read]"

    pages_text: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            pages_text.append(text)
        except Exception as e:
            pages_text.append(f"[Page {i + 1} unreadable: {e}]")

    combined = "\n".join(pages_text).strip()
    if not combined:
        return "[PDF contains no extractable text — it may be a scanned image]"
    return combined


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

    logger.info(
        "Starting grading — quest_id=%s submission_path=%s submission_text_len=%d",
        quest_data.get("individual_quest_id") or quest_data.get("quest_id"),
        submission_path,
        len(submission_text),
    )
    grading_input = _build_grading_input(quest_data, submission_text)
    try:
        result: GradingResult = asyncio.run(_grade(grading_input))
    except Exception as e:
        logger.error("Grading agent failed: %s", e, exc_info=True)
        raise

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
