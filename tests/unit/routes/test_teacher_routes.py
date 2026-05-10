"""API-level tests for /teacher routes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload


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
    @patch("routers.teacher.period_management_service")
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
    @patch("routers.teacher.period_management_service")
    def test_get_periods_empty(self, mock_svc, client):
        mock_svc.get_periods_by_owner.return_value = []
        resp = client.get("/teacher/periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == []

    @pytest.mark.api
    @patch("routers.teacher.period_management_service")
    def test_get_periods_service_error_returns_500(self, mock_svc, client):
        mock_svc.get_periods_by_owner.side_effect = RuntimeError("db error")
        resp = client.get("/teacher/periods")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /teacher/canvas/courses
# ---------------------------------------------------------------------------

class TestTeacherCanvasCourses:

    @pytest.mark.api
    @patch("routers.teacher.Canvas")
    def test_list_canvas_courses_success(self, mock_canvas, client):
        mock_course = MagicMock(id=1)
        mock_course.name = "Physics 101"
        mock_user = MagicMock()
        mock_user.get_courses.return_value = [mock_course]
        mock_canvas.return_value.get_current_user.return_value = mock_user

        resp = client.post(
            "/teacher/canvas/courses",
            json={"api_url": "https://canvas.example.com", "api_key": "token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "courses" in data
        assert data["courses"][0]["name"] == "Physics 101"
        mock_user.get_courses.assert_called_once_with(enrollment_type="teacher")

    @pytest.mark.api
    @patch("routers.teacher.Canvas")
    def test_list_canvas_courses_invalid_credentials(self, mock_canvas, client):
        mock_canvas.return_value.get_current_user.side_effect = Exception("bad creds")
        resp = client.post(
            "/teacher/canvas/courses",
            json={"api_url": "https://x.com", "api_key": "bad"},
        )
        assert resp.status_code == 400

