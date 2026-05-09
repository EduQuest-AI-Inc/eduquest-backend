"""Tests for the 7-day-out trial reminder pass."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.billing.trial_reminder_service import run_reminder_pass


@pytest.mark.unit
def test_reminder_skips_user_with_no_email():
    membership_dao = MagicMock()
    user_dao = MagicMock()
    email_svc = MagicMock()

    membership_dao.list_trialing_needing_reminder.return_value = [
        {"user_id": "u1", "trial_ends_at": "2026-05-30T00:00:00+00:00"}
    ]
    user_dao.get_by_id.return_value = {"first_name": "T", "email": None}

    res = run_reminder_pass(
        membership_dao=membership_dao,
        user_dao=user_dao,
        email_service=email_svc,
    )

    assert res.candidates == 1
    assert res.skipped_no_email == 1
    assert res.sent == 0
    email_svc.send_trial_reminder_email.assert_not_called()


@pytest.mark.unit
def test_reminder_sent_marks_membership():
    membership_dao = MagicMock()
    user_dao = MagicMock()
    email_svc = MagicMock()

    trial_ends = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    membership_dao.list_trialing_needing_reminder.return_value = [
        {"user_id": "u1", "trial_ends_at": trial_ends}
    ]
    user_dao.get_by_id.return_value = {"first_name": "T", "email": "t@eduquestai.org"}
    email_svc.send_trial_reminder_email.return_value = {
        "success": True, "message_id": "x"
    }

    res = run_reminder_pass(
        membership_dao=membership_dao,
        user_dao=user_dao,
        email_service=email_svc,
    )

    assert res.sent == 1
    assert res.failed == 0
    assert membership_dao.update.called
    args, _ = membership_dao.update.call_args
    assert args[0] == "u1"
    assert "reminder_sent_at" in args[1]


@pytest.mark.unit
def test_reminder_failure_does_not_mark_membership():
    membership_dao = MagicMock()
    user_dao = MagicMock()
    email_svc = MagicMock()

    membership_dao.list_trialing_needing_reminder.return_value = [
        {"user_id": "u1", "trial_ends_at": "2026-05-30T00:00:00+00:00"}
    ]
    user_dao.get_by_id.return_value = {"first_name": "T", "email": "t@eduquestai.org"}
    email_svc.send_trial_reminder_email.return_value = {
        "success": False, "error": "boom"
    }

    res = run_reminder_pass(
        membership_dao=membership_dao,
        user_dao=user_dao,
        email_service=email_svc,
    )

    assert res.failed == 1
    membership_dao.update.assert_not_called()
