"""Parent waitlist service.

Validates, persists, and dispatches confirmation emails for
homeschool-parent waitlist signups.

Compliance: no child PII is accepted, stored, or transmitted.
See supabase/migrations/003_parent_waitlist.sql.
"""

import logging
import re
from typing import Any, Dict, Optional
from data_access.supabase.parent_waitlist_dao import ParentWaitlistDAO

from models.parent_waitlist import ParentWaitlistEntry
from services.email_service import get_email_service

logger = logging.getLogger(__name__)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_MAX_NAME_LEN = 100
_MAX_CHALLENGE_LEN = 2000
_MAX_CONTACT_LEN = 200


class ParentWaitlistValidationError(ValueError):
    """Raised for any client-side validation failure."""


class ParentWaitlistService:
    def __init__(self) -> None:
        self._dao = ParentWaitlistDAO()
        self._email_service = get_email_service()

    # -- public ---------------------------------------------------------------

    def join(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate, persist, and send confirmation email."""
        entry = self._validate(payload)

        existing = self._dao.get_by_email(entry.email)
        if existing:
            return {"status": "already_signed_up"}

        try:
            self._dao.create(entry.to_row())
        except Exception as exc:  # unique-violation race or other insert error
            message = str(exc).lower()
            if "duplicate" in message or "unique" in message:
                return {"status": "already_signed_up"}
            raise

        # Email failure must not fail the signup — matches password-reset tolerance.
        try:
            result = self._email_service.send_parent_waitlist_confirmation(
                to_email=entry.email,
                first_name=entry.first_name,
            )
            if not result.get("success"):
                logger.warning(
                    "parent_waitlist: confirmation email failed for %s: %s",
                    entry.email,
                    result.get("error"),
                )
        except Exception:
            logger.exception(
                "parent_waitlist: unexpected error sending confirmation email to %s",
                entry.email,
            )

        return {"status": "ok"}

    # -- validation -----------------------------------------------------------

    def _validate(self, payload: Dict[str, Any]) -> ParentWaitlistEntry:
        if not isinstance(payload, dict):
            raise ParentWaitlistValidationError("invalid payload")

        first_name = _require_str(payload.get("first_name"), "first_name")
        last_name = _require_str(payload.get("last_name"), "last_name")
        email_raw = _require_str(payload.get("email"), "email")
        email = email_raw.strip().lower()

        if len(first_name) > _MAX_NAME_LEN or len(last_name) > _MAX_NAME_LEN:
            raise ParentWaitlistValidationError("name too long")
        if not _EMAIL_RE.match(email):
            raise ParentWaitlistValidationError("invalid email")

        num_children = _coerce_int(payload.get("num_children"), "num_children")
        if num_children < 0 or num_children > 20:
            raise ParentWaitlistValidationError("num_children out of range")

        learning_challenge = _optional_str(
            payload.get("learning_challenge"), _MAX_CHALLENGE_LEN
        )

        open_to_interview = bool(payload.get("open_to_interview", False))

        contact_method: Optional[str] = None
        if open_to_interview:
            contact_method = _optional_str(
                payload.get("contact_method"), _MAX_CONTACT_LEN
            )

        return ParentWaitlistEntry(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email,
            num_children=num_children,
            learning_challenge=learning_challenge,
            open_to_interview=open_to_interview,
            contact_method=contact_method,
        )


# -- helpers ------------------------------------------------------------------


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParentWaitlistValidationError(f"missing {field_name}")
    return value


def _optional_str(value: Any, max_len: int) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParentWaitlistValidationError("invalid field type")
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > max_len:
        raise ParentWaitlistValidationError("field too long")
    return trimmed


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ParentWaitlistValidationError(f"invalid {field_name}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ParentWaitlistValidationError(f"invalid {field_name}")
