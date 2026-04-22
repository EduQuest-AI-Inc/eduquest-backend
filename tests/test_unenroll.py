"""
Tests for the student unenroll flow: PeriodService.unenroll_from_period
and the POST /period/unenroll route.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_student(period_id="MATH-101", conversation_id="conv-abc"):
    return {
        "user_id": "stu-1",
        "enrollments": [period_id],
        "ltg_conversation_ids": {period_id: conversation_id},
        "long_term_goal": {"Precalculus": "Master derivatives"},
    }


def _build_period(period_id="MATH-101"):
    return {"period_id": period_id, "name": "Precalculus"}


class FakeWeeklyQuest:
    def __init__(self, quest_id) -> None:
        self.quest_id = quest_id


def _make_service():
    """Build a PeriodEnrollmentService with all DAO attributes replaced by mocks."""
    from routes.period.period_enrollment_service import PeriodEnrollmentService

    svc = PeriodEnrollmentService.__new__(PeriodEnrollmentService)
    svc.period_dao = MagicMock()
    svc.session_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.conversation_dao = MagicMock()
    svc.enrollment_dao = MagicMock()
    svc.period_schedule_dao = MagicMock()
    svc.weekly_quest_dao = MagicMock()
    svc.individual_quest_dao = MagicMock()
    svc.ltg_conversation_dao = MagicMock()
    svc.quest_service = MagicMock()
    return svc


def _setup_service(student, period, enrollments=None, weekly_quests=None, individual_quests=None, conversation_id="conv-abc"):
    svc = _make_service()

    svc.session_dao.get_sessions_by_auth_token.return_value = [{"user_id": student["user_id"]}]
    svc.student_dao.get_student_by_id.return_value = student
    svc.period_dao.get_period_by_id.return_value = period
    svc.enrollment_dao.get_enrollments_by_student.return_value = enrollments or [
        {"user_id": student["user_id"], "period_id": period["period_id"]}
    ]
    svc.ltg_conversation_dao.delete_conversation.return_value = conversation_id
    svc.weekly_quest_dao.get_quests_by_student_and_period.return_value = weekly_quests or []
    svc.individual_quest_dao.get_quests_by_student_and_period.return_value = individual_quests or []

    return svc


# ---------------------------------------------------------------------------
# Service-level unit tests
# ---------------------------------------------------------------------------

class TestUnenrollService:

    @pytest.mark.unit
    def test_unenroll_removes_enrollment(self) -> None:
        student = _build_student()
        svc = _setup_service(student, _build_period())

        result = svc.unenroll_from_period("tok", "MATH-101")

        assert result["period_id"] == "MATH-101"
        assert "MATH-101" not in result["remaining_enrollments"]

        svc.enrollment_dao.delete_enrollment.assert_called_once_with(
            "stu-1", "MATH-101"
        )

    @pytest.mark.unit
    def test_unenroll_deletes_conversation(self) -> None:
        svc = _setup_service(_build_student(), _build_period())

        svc.unenroll_from_period("tok", "MATH-101")

        svc.conversation_dao.delete_conversation.assert_called_once_with("conv-abc")

    @pytest.mark.unit
    def test_unenroll_deletes_quests(self) -> None:
        wq = FakeWeeklyQuest("wq-1")
        iq = [{"individual_quest_id": "iq-1"}, {"individual_quest_id": "iq-2"}]

        svc = _setup_service(_build_student(), _build_period(), weekly_quests=[wq], individual_quests=iq)

        svc.unenroll_from_period("tok", "MATH-101")

        svc.weekly_quest_dao.delete_weekly_quest.assert_called_once_with("wq-1")
        assert svc.individual_quest_dao.delete_individual_quest.call_count == 2

    @pytest.mark.unit
    def test_unenroll_removes_long_term_goal(self) -> None:
        svc = _setup_service(_build_student(), _build_period())

        svc.unenroll_from_period("tok", "MATH-101")

        calls = svc.student_dao.update_student.call_args_list
        goal_call = [c for c in calls if "long_term_goal" in c[0][1]]
        assert len(goal_call) == 1
        assert "Precalculus" not in goal_call[0][0][1]["long_term_goal"]

    @pytest.mark.unit
    def test_unenroll_not_enrolled_raises(self) -> None:
        student = _build_student(period_id="OTHER")
        svc = _setup_service(
            student, _build_period(),
            enrollments=[{"user_id": "stu-1", "period_id": "OTHER"}],
        )

        with pytest.raises(Exception, match="not enrolled"):
            svc.unenroll_from_period("tok", "MATH-101")

    @pytest.mark.unit
    def test_unenroll_missing_period_id_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(Exception, match="Missing period ID"):
            svc.unenroll_from_period("tok", "")

    @pytest.mark.unit
    def test_unenroll_invalid_token_raises(self) -> None:
        svc = _make_service()
        svc.session_dao.get_sessions_by_auth_token.return_value = []

        with pytest.raises(Exception, match="Invalid auth token"):
            svc.unenroll_from_period("bad-tok", "MATH-101")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from app import app as flask_app
    flask_app.config.update({"TESTING": True})
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


class TestUnenrollRoute:

    @pytest.mark.api
    @patch("routes.period.routes.period_service")
    def test_unenroll_endpoint_success(self, mock_service, client) -> None:
        mock_service.unenroll_from_period.return_value = {
            "message": "Successfully unenrolled from period MATH-101",
            "period_id": "MATH-101",
            "remaining_enrollments": [],
        }

        resp = client.post(
            "/period/unenroll",
            json={"period_id": "MATH-101"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["period_id"] == "MATH-101"

    @pytest.mark.api
    @patch("routes.period.routes.period_service")
    def test_unenroll_endpoint_missing_period(self, mock_service, client) -> None:
        resp = client.post(
            "/period/unenroll",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 400
        assert "period_id" in resp.get_json()["error"]

    @pytest.mark.api
    @patch("routes.period.routes.period_service")
    def test_unenroll_endpoint_not_enrolled(self, mock_service, client) -> None:
        from exceptions.validation_error import ValidationError
        mock_service.unenroll_from_period.side_effect = ValidationError("You are not enrolled in period X")

        resp = client.post(
            "/period/unenroll",
            json={"period_id": "X"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 400
