"""
Tests for the student unenroll flow: PeriodService.unenroll_from_period
and the POST /period/unenroll route.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from api.deps import get_auth, AuthPayload
from services.period.period_enrollment_service import PeriodEnrollmentService
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from typing import Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_student(period_id: str="MATH-101", conversation_id: str="conv-abc") -> Dict[str, Union[str, List[str], Dict[str, str]]]:
    return {
        "user_id": "stu-1",
        "enrollments": [period_id],
        "ltg_conversation_ids": {period_id: conversation_id},
        "long_term_goal": {"Precalculus": "Master derivatives"},
    }


def _build_period(period_id: str="MATH-101") -> Dict[str, str]:
    return {"period_id": period_id, "name": "Precalculus"}


class FakeWeeklyQuest:
    def __init__(self, quest_id: str) -> None:
        self.quest_id = quest_id


def _make_service() -> PeriodEnrollmentService:
    """Build a PeriodEnrollmentService with all DAO attributes replaced by mocks."""
    from services.period.period_enrollment_service import PeriodEnrollmentService

    svc = PeriodEnrollmentService.__new__(PeriodEnrollmentService)
    svc.period_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.conversation_dao = MagicMock()
    svc.enrollment_dao = MagicMock()
    svc.ltg_conversation_dao = MagicMock()
    svc.ltg_goal_dao = MagicMock()
    svc.quest_dao = MagicMock()
    return svc


def _setup_service(student: Dict[str, Union[str, List[str], Dict[str, str]]], period: Dict[str, str], enrollments: Optional[List[Dict[str, str]]]=None, weekly_quests: Optional[List[FakeWeeklyQuest]]=None, individual_quests: Optional[List[Dict[str, str]]]=None, conversation_id: str="conv-abc") -> PeriodEnrollmentService:
    svc = _make_service()

    svc.student_dao.get_student_by_id.return_value = student
    svc.period_dao.get_period_by_id.return_value = period
    svc.enrollment_dao.get_enrollments_by_student.return_value = enrollments or [
        {"user_id": student["user_id"], "period_id": period["period_id"]}
    ]
    svc.ltg_conversation_dao.delete_conversation.return_value = conversation_id
    svc.quest_dao.get_quests_by_student_and_period.return_value = [
        {"quest_id": q.quest_id} for q in (weekly_quests or [])
    ] + [{"quest_id": iq.get("individual_quest_id", iq.get("quest_id", ""))} for iq in (individual_quests or [])]

    return svc


# ---------------------------------------------------------------------------
# Service-level unit tests
# ---------------------------------------------------------------------------

class TestUnenrollService:

    @pytest.mark.unit
    def test_unenroll_removes_enrollment(self) -> None:
        student = _build_student()
        svc = _setup_service(student, _build_period())

        result = svc.unenroll_from_period("stu-1", "MATH-101")

        assert result["period_id"] == "MATH-101"
        assert "MATH-101" not in result["remaining_enrollments"]

        svc.enrollment_dao.delete_enrollment.assert_called_once_with(
            "stu-1", "MATH-101"
        )

    @pytest.mark.unit
    def test_unenroll_deletes_conversation(self) -> None:
        svc = _setup_service(_build_student(), _build_period())

        svc.unenroll_from_period("stu-1", "MATH-101")

        svc.conversation_dao.delete_conversation.assert_called_once_with("conv-abc")

    @pytest.mark.unit
    def test_unenroll_deletes_quests(self) -> None:
        wq = FakeWeeklyQuest("wq-1")
        iq = [{"individual_quest_id": "iq-1"}, {"individual_quest_id": "iq-2"}]

        svc = _setup_service(_build_student(), _build_period(), weekly_quests=[wq], individual_quests=iq)

        svc.unenroll_from_period("stu-1", "MATH-101")

        # After the step-3 refactor, quests are deleted via quest_dao.delete_quest.
        assert svc.quest_dao.delete_quest.call_count == 3  # 1 weekly + 2 individual

    @pytest.mark.unit
    def test_unenroll_removes_long_term_goal(self) -> None:
        svc = _setup_service(_build_student(), _build_period())

        svc.unenroll_from_period("stu-1", "MATH-101")

        # After the step-3/4 refactor, long-term goals are deleted via ltg_goal_dao.delete.
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


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

def _fake_auth():
    return AuthPayload(sub="stu-1", role="student", token="fake-token")


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = _fake_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestUnenrollRoute:

    @pytest.mark.api
    @patch("api.routers.period.period_service")
    def test_unenroll_endpoint_success(self, mock_service: MagicMock, client) -> None:
        mock_service.unenroll_from_period.return_value = {
            "message": "Successfully unenrolled from period MATH-101",
            "period_id": "MATH-101",
            "remaining_enrollments": [],
        }
        resp = client.post("/period/unenroll", json={"period_id": "MATH-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_id"] == "MATH-101"

    @pytest.mark.api
    @patch("api.routers.period.period_service")
    def test_unenroll_endpoint_missing_period(self, mock_service: MagicMock, client) -> None:
        resp = client.post("/period/unenroll", json={})
        assert resp.status_code == 422  # FastAPI returns 422 for missing required fields

    @pytest.mark.api
    @patch("api.routers.period.period_service")
    def test_unenroll_endpoint_not_enrolled(self, mock_service: MagicMock, client) -> None:
        from exceptions.validation_error import ValidationError
        mock_service.unenroll_from_period.side_effect = ValidationError("You are not enrolled in period X")
        resp = client.post("/period/unenroll", json={"period_id": "X"})
        assert resp.status_code == 400
