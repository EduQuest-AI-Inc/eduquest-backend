from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.auth.student_compliance_outreach_service import StudentComplianceOutreachService


def _service() -> StudentComplianceOutreachService:
    return StudentComplianceOutreachService(
        student_dao=MagicMock(),
        parent_dao=MagicMock(),
        user_dao=MagicMock(),
        email_service=MagicMock(),
    )


@pytest.mark.unit
def test_outreach_refuses_to_send_without_approved_copy(monkeypatch):
    monkeypatch.setenv("STUDENT_COMPLIANCE_OUTREACH_ENABLED", "true")
    monkeypatch.delenv("STUDENT_COMPLIANCE_OUTREACH_COPY_APPROVED", raising=False)

    with pytest.raises(RuntimeError, match="Counsel-approved"):
        _service().run_pass()


@pytest.mark.unit
def test_outreach_sends_initial_notice_to_student_and_linked_parent(monkeypatch):
    monkeypatch.setenv("STUDENT_COMPLIANCE_OUTREACH_ENABLED", "true")
    monkeypatch.setenv("STUDENT_COMPLIANCE_OUTREACH_COPY_APPROVED", "true")
    now = datetime.now(timezone.utc)
    service = _service()
    service.student_dao.list_legacy_review_due.return_value = [{
        "user_id": "student-1",
        "email": "student@example.com",
        "compliance_review_due_at": (now + timedelta(days=21)).isoformat(),
        "compliance_outreach_stage": 0,
    }]
    service.parent_dao.get_parents_by_student_id.return_value = [{"user_id": "parent-1"}]
    service.user_dao.get_by_id.return_value = {"email": "parent@example.com"}
    service.email_service.send_student_compliance_outreach_email.return_value = {"success": True}

    result = service.run_pass(now)

    assert result.sent == 2
    recipients = {
        call.kwargs["to_email"]
        for call in service.email_service.send_student_compliance_outreach_email.call_args_list
    }
    assert recipients == {"student@example.com", "parent@example.com"}
    service.student_dao.update_student.assert_called_once()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("days_remaining", "expected"),
    [(21, 1), (14, 2), (7, 3), (1, 4), (-1, 4)],
)
def test_outreach_stage_schedule(days_remaining, expected):
    assert StudentComplianceOutreachService._stage_for_days_remaining(days_remaining) == expected
