"""API-level tests for /teacher routes."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from api.deps import get_auth, AuthPayload


def _teacher_auth():
    return AuthPayload(sub="teacher-1", role="teacher", token="fake-token")


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = _teacher_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /teacher/periods
# ---------------------------------------------------------------------------

class TestGetTeacherPeriods:

    @pytest.mark.api
    @patch("api.routers.teacher.period_management_service")
    def test_get_periods_success(self, mock_svc, client):
        mock_svc.get_periods_by_owner.return_value = [
            {"period_id": "P1", "name": "Math"},
            {"period_id": "P2", "name": "Science"},
        ]
        resp = client.get("/teacher/periods")
        assert resp.status_code == 200
        data = resp.json()
        assert "periods" in data
        assert len(data["periods"]) == 2

    @pytest.mark.api
    @patch("api.routers.teacher.period_management_service")
    def test_get_periods_empty(self, mock_svc, client):
        mock_svc.get_periods_by_owner.return_value = []
        resp = client.get("/teacher/periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == []

    @pytest.mark.api
    @patch("api.routers.teacher.period_management_service")
    def test_get_periods_service_error_returns_500(self, mock_svc, client):
        mock_svc.get_periods_by_owner.side_effect = RuntimeError("db error")
        resp = client.get("/teacher/periods")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /teacher/period-schedule
# ---------------------------------------------------------------------------

class TestGetPeriodSchedule:

    @pytest.mark.api
    @patch("api.routers.teacher.period_schedule_service")
    def test_get_schedule_success(self, mock_svc, client):
        mock_svc.get_schedule.return_value = {
            "period_id": "P1",
            "weeks": [{"week": 1, "topic": "Intro"}],
        }
        resp = client.get("/teacher/period-schedule", params={"period_id": "P1"})
        assert resp.status_code == 200
        assert resp.json()["period_id"] == "P1"

    @pytest.mark.api
    @patch("api.routers.teacher.period_schedule_service")
    def test_get_schedule_not_found(self, mock_svc, client):
        mock_svc.get_schedule.return_value = None
        resp = client.get("/teacher/period-schedule", params={"period_id": "MISSING"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_get_schedule_missing_period_id(self, client):
        resp = client.get("/teacher/period-schedule")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /teacher/period-schedule
# ---------------------------------------------------------------------------

class TestUpdatePeriodSchedule:

    @pytest.mark.api
    @patch("api.routers.teacher.period_schedule_service")
    def test_update_schedule_success(self, mock_svc, client):
        mock_svc.update_schedule.return_value = {"period_id": "P1", "updated": True}
        resp = client.put("/teacher/period-schedule", json={
            "period_id": "P1",
            "schedule": {"weeks": [{"week": 1, "topic": "Updated"}]},
        })
        assert resp.status_code == 200
        assert resp.json()["period_id"] == "P1"

    @pytest.mark.api
    @patch("api.routers.teacher.period_schedule_service")
    def test_update_schedule_permission_denied(self, mock_svc, client):
        mock_svc.update_schedule.side_effect = PermissionError("Not your period")
        resp = client.put("/teacher/period-schedule", json={
            "period_id": "OTHER", "schedule": {}
        })
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /teacher/period-schedule/quest-weeks
# ---------------------------------------------------------------------------

class TestSetQuestWeeks:

    @pytest.mark.api
    @patch("api.routers.teacher.period_schedule_service")
    def test_set_quest_weeks_success(self, mock_svc, client):
        mock_svc.set_quest_weeks.return_value = {"period_id": "P1", "quest_enabled_weeks": [1, 3, 5]}
        resp = client.put("/teacher/period-schedule/quest-weeks", json={
            "period_id": "P1",
            "quest_enabled_weeks": [1, 3, 5],
        })
        assert resp.status_code == 200
        assert resp.json()["quest_enabled_weeks"] == [1, 3, 5]

    @pytest.mark.api
    @patch("api.routers.teacher.period_schedule_service")
    def test_set_quest_weeks_invalid_period(self, mock_svc, client):
        mock_svc.set_quest_weeks.side_effect = ValueError("Period not found")
        resp = client.put("/teacher/period-schedule/quest-weeks", json={
            "period_id": "BAD", "quest_enabled_weeks": [1]
        })
        assert resp.status_code == 400
