"""API-level tests for /user routes (profile, tutorial, canvas removal)."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload


def _student_auth():
    return AuthPayload(sub="stu-1", role="student", token="fake-token")


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = _student_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /user/profile
# ---------------------------------------------------------------------------

class TestGetProfile:

    @pytest.mark.api
    def test_get_profile_success(self, client):
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"user_id": "stu-1", "role": "student"}
        mock_svc.get_student_by_id.return_value = {
            "user_id": "stu-1",
            "first_name": "Jane",
            "last_name": "Doe",
            "grade": 10,
            "strength": ["math", "science"],
            "weakness": ["writing"],
            "interest": ["robotics"],
            "learning_style": ["visual"],
            "completed_tutorial": False,
        }
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.get("/user/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "stu-1"
        assert data["role"] == "student"
        assert data["grade"] == 10
        assert data["strength"] == ["math", "science"]

    @pytest.mark.api
    def test_get_profile_user_not_found(self, client):
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = None
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.get("/user/profile")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_get_profile_strips_teacher_canvas_key(self, client):
        app.dependency_overrides[get_auth] = lambda: AuthPayload(sub="tch-1", role="teacher", token="fake-token")
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"user_id": "tch-1", "role": "teacher"}
        mock_svc.get_teacher_by_id.return_value = {
            "user_id": "tch-1",
            "canvas_api_key": "secret",
        }
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.get("/user/profile")
        app.dependency_overrides[get_auth] = _student_auth
        assert resp.status_code == 200
        assert "canvas_api_key" not in resp.json()


# ---------------------------------------------------------------------------
# POST /user/update-tutorial
# ---------------------------------------------------------------------------

class TestUpdateTutorial:

    @pytest.mark.api
    def test_update_tutorial_success(self, client):
        mock_svc = MagicMock()
        mock_svc.update_tutorial_status.return_value = None
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.post("/user/update-tutorial", json={"completed_tutorial": True})
        assert resp.status_code == 200
        assert "updated" in resp.json()["message"]

    @pytest.mark.api
    def test_update_tutorial_defaults_false(self, client):
        mock_svc = MagicMock()
        mock_svc.update_tutorial_status.return_value = None
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.post("/user/update-tutorial", json={})
        assert resp.status_code == 200
        mock_svc.update_tutorial_status.assert_called_with("stu-1", False)


# ---------------------------------------------------------------------------
# GET /user/tutorial-status
# ---------------------------------------------------------------------------

class TestGetTutorialStatus:

    @pytest.mark.api
    def test_tutorial_status_complete(self, client):
        mock_svc = MagicMock()
        mock_svc.get_tutorial_status.return_value = True
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.get("/user/tutorial-status")
        assert resp.status_code == 200
        assert resp.json()["completed_tutorial"] is True

    @pytest.mark.api
    def test_tutorial_status_incomplete(self, client):
        mock_svc = MagicMock()
        mock_svc.get_tutorial_status.return_value = False
        with patch("routers.user.UserService", return_value=mock_svc):
            resp = client.get("/user/tutorial-status")
        assert resp.status_code == 200
        assert resp.json()["completed_tutorial"] is False


# ---------------------------------------------------------------------------
# Student Canvas endpoints removed
# ---------------------------------------------------------------------------

class TestStudentCanvasEndpointsRemoved:

    @pytest.mark.api
    def test_canvas_connect_returns_404(self, client):
        resp = client.post("/user/canvas/connect", json={"api_url": "https://x.com", "api_key": "tok"})
        assert resp.status_code in (404, 405)

    @pytest.mark.api
    def test_canvas_courses_returns_404(self, client):
        resp = client.get("/user/canvas/courses")
        assert resp.status_code in (404, 405)

    @pytest.mark.api
    def test_canvas_disconnect_returns_404(self, client):
        resp = client.delete("/user/canvas/disconnect")
        assert resp.status_code in (404, 405)
