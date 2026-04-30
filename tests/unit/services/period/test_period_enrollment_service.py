import pytest
from unittest.mock import MagicMock
from typing import Dict, List, Optional, Union

from services.enrollment.enrollment_service import EnrollmentService
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_student(period_id: str = "MATH-101", conversation_id: str = "conv-abc") -> Dict[str, Union[str, List[str], Dict[str, str]]]:
    return {
        "user_id": "stu-1",
        "enrollments": [period_id],
        "ltg_conversation_ids": {period_id: conversation_id},
        "long_term_goal": {"Precalculus": "Master derivatives"},
    }


def _build_period(period_id: str = "MATH-101") -> Dict[str, str]:
    return {"period_id": period_id, "name": "Precalculus"}


def _make_service() -> EnrollmentService:
    svc = EnrollmentService.__new__(EnrollmentService)
    svc.period_dao = MagicMock()
    svc.period_schedule_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.user_dao = MagicMock()
    svc.conversation_dao = MagicMock()
    svc.enrollment_dao = MagicMock()
    svc.ltg_conversation_dao = MagicMock()
    svc.ltg_goal_dao = MagicMock()
    svc.quest_dao = MagicMock()
    return svc


def _setup_service(
    student: Dict[str, Union[str, List[str], Dict[str, str]]],
    period: Dict[str, str],
    enrollments: Optional[List[Dict[str, str]]] = None,
    quests: Optional[List[Dict[str, str]]] = None,
    conversation_id: str = "conv-abc",
) -> EnrollmentService:
    svc = _make_service()
    svc.student_dao.get_student_by_id.return_value = student
    svc.period_dao.get_period_by_id.return_value = period
    svc.enrollment_dao.get_enrollments_by_student.return_value = enrollments or [
        {"user_id": student["user_id"], "period_id": period["period_id"]}
    ]
    svc.ltg_conversation_dao.delete_conversation.return_value = conversation_id
    svc.quest_dao.get_quests_by_student_and_period.return_value = quests or []
    return svc


# ---------------------------------------------------------------------------
# Unenroll service tests
# ---------------------------------------------------------------------------

class TestUnenrollService:

    @pytest.mark.unit
    def test_unenroll_removes_enrollment(self) -> None:
        student = _build_student()
        svc = _setup_service(student, _build_period())

        result = svc.unenroll_from_period("stu-1", "MATH-101")

        assert result["period_id"] == "MATH-101"
        assert "MATH-101" not in result["remaining_enrollments"]
        svc.enrollment_dao.delete_enrollment.assert_called_once_with("stu-1", "MATH-101")

    @pytest.mark.unit
    def test_unenroll_deletes_conversation(self) -> None:
        svc = _setup_service(_build_student(), _build_period())

        svc.unenroll_from_period("stu-1", "MATH-101")

        svc.conversation_dao.delete_conversation.assert_called_once_with("conv-abc")

    @pytest.mark.unit
    def test_unenroll_deletes_quests(self) -> None:
        quests = [
            {"quest_id": "wq-1"},
            {"quest_id": "iq-1"},
            {"quest_id": "iq-2"},
        ]
        svc = _setup_service(_build_student(), _build_period(), quests=quests)

        svc.unenroll_from_period("stu-1", "MATH-101")

        assert svc.quest_dao.delete_quest.call_count == 3

    @pytest.mark.unit
    def test_unenroll_removes_long_term_goal(self) -> None:
        svc = _setup_service(_build_student(), _build_period())

        svc.unenroll_from_period("stu-1", "MATH-101")

        svc.ltg_goal_dao.delete.assert_called_once_with("stu-1", "MATH-101")

    @pytest.mark.unit
    def test_unenroll_not_enrolled_raises(self) -> None:
        student = _build_student(period_id="OTHER")
        svc = _setup_service(
            student, _build_period(),
            enrollments=[{"user_id": "stu-1", "period_id": "OTHER"}],
        )

        with pytest.raises(ValidationError, match="not enrolled"):
            svc.unenroll_from_period("stu-1", "MATH-101")

    @pytest.mark.unit
    def test_unenroll_missing_period_id_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(ValidationError, match="Missing period ID"):
            svc.unenroll_from_period("stu-1", "")

    @pytest.mark.unit
    def test_unenroll_student_not_found_raises(self) -> None:
        svc = _make_service()
        svc.student_dao.get_student_by_id.return_value = None

        with pytest.raises(NotFoundError, match="Student not found"):
            svc.unenroll_from_period("unknown-user", "MATH-101")


@pytest.mark.unit
def test_get_my_periods_success():
    svc = _make_service()
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
    svc = _make_service()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "gone"}]
    svc.ltg_goal_dao.get_by_student.return_value = {}
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.get_my_periods("u1")

    assert result == []


def _setup_verify(svc: EnrollmentService, *, owner_role: str = "teacher") -> None:
    schedule_mock = MagicMock()
    schedule_mock.quest_enabled_weeks = True
    svc.period_schedule_dao.get_by_period_id.return_value = schedule_mock
    svc.user_dao.get_by_id.return_value = {"role": owner_role}


@pytest.mark.unit
def test_verify_period_id_not_enrolled_enrolls_student():
    svc = _make_service()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "name": "Math", "owner_id": "t1"}
    _setup_verify(svc)
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = []

    result = svc.verify_period_id("u1", "p1")

    svc.enrollment_dao.add_enrollment.assert_called_once()
    assert result["period_id"] == "p1"


@pytest.mark.unit
def test_verify_period_id_already_enrolled_raises():
    svc = _make_service()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "t1"}
    _setup_verify(svc)
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p1"}]

    with pytest.raises(ValidationError):
        svc.verify_period_id("u1", "p1")


@pytest.mark.unit
def test_verify_rejects_parent_period_via_id():
    svc = _make_service()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "par1"}
    _setup_verify(svc, owner_role="parent")

    with pytest.raises(NotFoundError):
        svc.verify_period_id("u1", "p1")


@pytest.mark.unit
def test_verify_allows_parent_period_via_dropdown():
    svc = _make_service()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "name": "Math", "owner_id": "par1"}
    _setup_verify(svc, owner_role="parent")
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = []

    result = svc.verify_period_id("u1", "p1", allow_parent_period=True)

    svc.enrollment_dao.add_enrollment.assert_called_once()
    assert result["period_id"] == "p1"


@pytest.mark.unit
def test_assert_enrolled_success():
    svc = _make_service()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [
        {"user_id": "u1"}, {"user_id": "u2"}
    ]

    svc.assert_enrolled("u1", "p1")  # should not raise


@pytest.mark.unit
def test_assert_enrolled_fails():
    svc = _make_service()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "u2"}]

    with pytest.raises(ValidationError, match="not enrolled"):
        svc.assert_enrolled("u1", "p1")
