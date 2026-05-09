"""
Trial-reminder job.

Finds parent/teacher memberships whose 14-day trial ends in 7 days or less
(and that haven't already been reminded) and emails the owner an actionable
"subscribe now" notice.

Designed to be called once a day from cron / Supabase pg_cron / a scheduled
task. Idempotent: each membership is reminded at most once via
membership.reminder_sent_at.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from data_access.membership_dao import MembershipDAO
from data_access.user_dao import UserDAO
from integrations.email_service import get_email_service
from services.billing.membership_service import REMINDER_LEAD_DAYS

logger = logging.getLogger(__name__)


@dataclass
class ReminderRunResult:
    candidates: int
    sent: int
    skipped_no_email: int
    failed: int


def run_reminder_pass(
    now: Optional[datetime] = None,
    *,
    membership_dao: Optional[MembershipDAO] = None,
    user_dao: Optional[UserDAO] = None,
    email_service=None,
) -> ReminderRunResult:
    """Send 7-day-out trial reminders. Returns counts for observability."""
    now = now or datetime.now(timezone.utc)
    cutoff = now + timedelta(days=REMINDER_LEAD_DAYS)
    cutoff_iso = cutoff.isoformat()

    membership_dao = membership_dao or MembershipDAO()
    user_dao = user_dao or UserDAO()
    email_service = email_service or get_email_service()

    candidates = membership_dao.list_trialing_needing_reminder(cutoff_iso)
    sent = 0
    skipped_no_email = 0
    failed = 0

    for record in candidates:
        user_id = record["user_id"]
        user = user_dao.get_by_id(user_id)
        if not user or not user.get("email"):
            skipped_no_email += 1
            continue

        trial_ends_at = record.get("trial_ends_at")
        days_left = REMINDER_LEAD_DAYS
        try:
            if trial_ends_at:
                end_dt = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
                days_left = max((end_dt - now).days, 1)
        except ValueError:
            pass

        result = email_service.send_trial_reminder_email(
            to_email=user["email"],
            first_name=user.get("first_name", ""),
            days_left=days_left,
        )
        if result.get("success"):
            membership_dao.update(user_id, {"reminder_sent_at": now.isoformat()})
            sent += 1
        else:
            failed += 1

    logger.info(
        "trial_reminder.pass candidates=%d sent=%d skipped_no_email=%d failed=%d",
        len(candidates), sent, skipped_no_email, failed,
    )
    return ReminderRunResult(
        candidates=len(candidates),
        sent=sent,
        skipped_no_email=skipped_no_email,
        failed=failed,
    )
