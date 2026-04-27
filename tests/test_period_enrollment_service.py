"""
Extends coverage beyond test_unenroll.py.
test_unenroll.py already covers all unenroll_from_period cases.
These tests cover get_my_periods, verify_period_id, and assert_enrolled.
"""
import pytest
from unittest.mock import MagicMock

from services.period.period_enrollment_service import PeriodEnrollmentService


def _svc():
    svc = PeriodEnrollmentService.__new__(PeriodEnrollmentService)
    svc.period_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.enrollment_dao = MagicMock()
    svc.quest_dao = MagicMock()
    svc.ltg_conversation_dao = MagicMock()
    svc.conversation_dao = MagicMock()
    svc.ltg_goal_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_get_my_periods_success():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": "p1"},
        {"period_id": "p2"},
    ]
    svc.ltg_goal_dao.get_by_student.return_value = {"p1": "Be a doctor"}
    svc.period_dao.get_period_by_id.side_effect = [
        {"period_id": "p1", "name": "Math"},
        {"period_id": "p2", "name": "Science"},
    ]

    result = svc.get_my_periods("u1")

    assert len(result) == 2
    assert result[0]["period_id"] == "p1"
    assert result[0]["long_term_goal"] == "Be a doctor"
    assert result[1]["long_term_goal"] is None


@pytest.mark.unit
def test_get_my_periods_skips_missing_periods():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "gone"}]
    svc.ltg_goal_dao.get_by_student.return_value = {}
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.get_my_periods("u1")

    assert result == []


@pytest.mark.unit
def test_verify_period_id_not_enrolled_enrolls_student():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "name": "Math"}
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = []

    result = svc.verify_period_id("u1", "p1")

    svc.enrollment_dao.add_enrollment.assert_called_once()
    assert result["period_id"] == "p1"


@pytest.mark.unit
def test_verify_period_id_already_enrolled_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p1"}]

    with pytest.raises(Exception):
        svc.verify_period_id("u1", "p1")


@pytest.mark.unit
def test_assert_enrolled_success():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [
        {"user_id": "u1"}, {"user_id": "u2"}
    ]

    svc.assert_enrolled("u1", "p1")  # should not raise


@pytest.mark.unit
def test_assert_enrolled_fails():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "u2"}]

    with pytest.raises(Exception, match="not enrolled"):
        svc.assert_enrolled("u1", "p1")
