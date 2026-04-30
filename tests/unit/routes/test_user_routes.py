"""API-level tests for /user routes (profile, tutorial, canvas removal)."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from api.deps import get_auth, AuthPayload


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
    @patch("api.routers.user.user_dao")
    @patch("api.routers.user.student_dao")
    def test_get_profile_success(self, mock_student_dao, mock_user_dao, client):
        mock_user_dao.get_by_id.return_value = {"user_id": "stu-1", "role": "student"}
        mock_student_dao.get_student_by_id.return_value = {
            "user_id": "stu-1",
            "first_name": "Jane",
            "last_name": "Doe",
            "grade": "10",
        }
        resp = client.get("/user/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "stu-1"
        assert data["role"] == "student"

    @pytest.mark.api
    @patch("api.routers.user.user_dao")
    def test_get_profile_user_not_found(self, mock_user_dao, client):
        mock_user_dao.get_by_id.return_value = None
        resp = client.get("/user/profile")
        assert resp.status_code == 404

    @pytest.mark.api
    @patch("api.routers.user.user_dao")
    @patch("api.routers.user.student_dao")
    def test_get_profile_strips_canvas_key(self, mock_student_dao, mock_user_dao, client):
        mock_user_dao.get_by_id.return_value = {"user_id": "stu-1", "role": "student"}
        mock_student_dao.get_student_by_id.return_value = {
            "user_id": "stu-1",
            "canvas_api_key": "secret",
            "grade": "10",
        }
        resp = client.get("/user/profile")
        assert resp.status_code == 200
        assert "canvas_api_key" not in resp.json()


# ---------------------------------------------------------------------------
# POST /user/update-tutorial
# ---------------------------------------------------------------------------

class TestUpdateTutorial:

    @pytest.mark.api
    @patch("api.routers.user.user_service")
    def test_update_tutorial_success(self, mock_svc, client):
        mock_svc.update_tutorial_status.return_value = None
        resp = client.post("/user/update-tutorial", json={"completed_tutorial": True})
        assert resp.status_code == 200
        assert "updated" in resp.json()["message"]

    @pytest.mark.api
    @patch("api.routers.user.user_service")
    def test_update_tutorial_defaults_false(self, mock_svc, client):
        mock_svc.update_tutorial_status.return_value = None
        resp = client.post("/user/update-tutorial", json={})
        assert resp.status_code == 200
        mock_svc.update_tutorial_status.assert_called_with("stu-1", False)


# ---------------------------------------------------------------------------
# GET /user/tutorial-status
# ---------------------------------------------------------------------------

class TestGetTutorialStatus:

    @pytest.mark.api
    @patch("api.routers.user.user_service")
    def test_tutorial_status_complete(self, mock_svc, client):
        mock_svc.get_tutorial_status.return_value = True
        resp = client.get("/user/tutorial-status")
        assert resp.status_code == 200
        assert resp.json()["completed_tutorial"] is True

    @pytest.mark.api
    @patch("api.routers.user.user_service")
    def test_tutorial_status_incomplete(self, mock_svc, client):
        mock_svc.get_tutorial_status.return_value = False
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
