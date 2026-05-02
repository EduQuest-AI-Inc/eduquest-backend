"""
Backend wrapper for PostHog identify / group_identify / capture.

Hard guarantees enforced here so call sites stay simple:

  1. distinct_id is ALWAYS the canonical Supabase user_id, never email.
  2. Internal users (staff, e2e accounts) are dropped: by `is_internal` flag
     OR by email suffix (@test.org, @eduquestai.org).
  3. Free-text / PII property keys (goal_text, course_name, file_name, …)
     are stripped before send. FERPA / COPPA driven.
  4. Period-scoped events (anything with `period_id` in properties) auto-
     attach `groups={"period": <period_id>}`.
  5. Analytics errors NEVER raise into the request handler.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from .posthog_client import get_posthog

logger = logging.getLogger(__name__)

# ----- Internal-user guard ----------------------------------------------------

INTERNAL_EMAIL_SUFFIXES = ("@test.org", "@eduquestai.org")


def _is_internal(email: Optional[str], is_internal_flag: Optional[bool]) -> bool:
    if is_internal_flag:
        return True
    if email and any(email.lower().endswith(s) for s in INTERNAL_EMAIL_SUFFIXES):
        return True
    return False


# ----- PII / free-text guard --------------------------------------------------

PII_KEYS = frozenset(
    {
        "goal_text",
        "course_name",
        "email",
        "name",
        "first_name",
        "last_name",
        "submission_text",
        "submission_content",
        "feedback",
        "feedback_text",
        "file_name",
        "filename",
        "chat_message",
        "message_text",
        "answer",
    }
)


def _sanitize(props: Mapping[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    dropped: list[str] = []
    for k, v in props.items():
        if k in PII_KEYS:
            dropped.append(k)
            continue
        if v is None:
            continue
        cleaned[k] = v
    if dropped:
        # Loud-and-fast in dev (DEBUG-level), silent in prod.
        logger.debug("dropped PII keys from event payload: %s", dropped)
    return cleaned


# ----- Public API -------------------------------------------------------------


def track_event(
    *,
    user_id: str,
    event: str,
    properties: Optional[Mapping[str, Any]] = None,
    user_email: Optional[str] = None,
    is_internal: Optional[bool] = None,
) -> None:
    """
    Capture a PostHog event from the backend.

    Args:
        user_id: Canonical Supabase user_id. Required. Never email.
        event: Event name (use `Events.X` from `events.py`).
        properties: Structural metadata. PII keys will be stripped.
        user_email: Optional, used only for the internal-user guard.
        is_internal: Optional, internal-user guard short-circuit.
    """
    if not user_id:
        logger.warning("track_event called without user_id; dropping event=%s", event)
        return

    if _is_internal(user_email, is_internal):
        return

    props = _sanitize(properties or {})
    groups: dict[str, str] = {}
    period_id = props.get("period_id")
    if isinstance(period_id, str) and period_id:
        groups["period"] = period_id

    try:
        get_posthog().capture(
            distinct_id=user_id,
            event=event,
            properties=props,
            groups=groups or None,
        )
    except Exception:  # pragma: no cover
        logger.exception("posthog capture failed for event=%s", event)


def identify_user(
    *,
    user_id: str,
    traits: Mapping[str, Any],
) -> None:
    """
    Update a user's traits in PostHog. Use sparingly from the backend —
    most identify() calls happen on the frontend (`UserProvider`).
    The backend's main job here is the daily snapshot sync.

    `email` may be in traits (PII trait, allowed). Internal users are dropped.
    """
    if not user_id:
        return
    if _is_internal(traits.get("email"), traits.get("is_internal")):
        return
    try:
        get_posthog().identify(distinct_id=user_id, properties=dict(traits))
    except Exception:  # pragma: no cover
        logger.exception("posthog identify failed for user_id=%s", user_id)


def group_identify_period(
    *,
    period_id: str,
    traits: Mapping[str, Any],
) -> None:
    """
    Update traits for a `period` (class) group. EduQuest's only group type.
    Used by:
      - period creation route
      - canvas connect/disconnect routes
      - schedule_generated event
      - daily snapshot sync
    """
    if not period_id:
        return
    try:
        get_posthog().group_identify(
            group_type="period",
            group_key=period_id,
            properties=dict(traits),
        )
    except Exception:  # pragma: no cover
        logger.exception("posthog group_identify failed for period_id=%s", period_id)
