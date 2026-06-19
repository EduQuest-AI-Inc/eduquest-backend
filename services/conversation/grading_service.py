"""
Grading service — wires the GradingOrchestrator into Flask.

Handles file I/O for student submissions and delegates all grading
logic to the bots layer via BotProvider.grade_submission().
"""
import asyncio
import logging
from typing import Dict, Any, Optional

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from bots.protocol import BotProviderProtocol
from exceptions.validation_error import ValidationError
from services.tracking import Events, track_event

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


def grade_student_submission(
    quest_data: Dict[str, Any],
    submission_path: Optional[str] = None,
    submission_text: Optional[str] = None,
    *,
    bot_provider: BotProviderProtocol,
) -> Dict[str, Any]:
    """
    Synchronous entry-point called from ``ConversationService``.

    Accepts either a file path or raw text for the submission.
    All grading logic (input construction, orchestration, result formatting)
    is handled by BotProvider.grade_submission().
    """
    if submission_text is None:
        if submission_path is None:
            raise ValidationError("Either submission_path or submission_text is required")
        submission_text = _read_submission_text(submission_path)

    logger.info(
        "Starting grading — quest_id=%s submission_path=%s submission_text_len=%d",
        quest_data.get("individual_quest_id") or quest_data.get("quest_id"),
        submission_path,
        len(submission_text),
    )
    try:
        return asyncio.run(bot_provider.grade_submission(quest_data, submission_text))
    except Exception as e:
        logger.error("Grading agent failed: %s", e, exc_info=True)
        user_id = quest_data.get("user_id") or ""
        if user_id:
            track_event(
                user_id=user_id,
                event=Events.QUEST_GRADING_FAILED,
                properties={
                    "quest_id": quest_data.get("individual_quest_id") or quest_data.get("quest_id"),
                    "period_id": quest_data.get("period_id"),
                    "error_type": type(e).__name__,
                    "no_ad_targeting": True,
                    "student_data": True,
                },
            )
        raise
