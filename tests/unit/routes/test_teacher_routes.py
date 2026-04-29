"""API-level tests for /teacher routes."""
import pytest
from unittest.mock import patch
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

