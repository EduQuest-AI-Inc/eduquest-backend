"""API-level tests for /auth routes."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

class TestSignupRoute:

    @pytest.mark.api
    @patch("api.routers.auth.register_user", return_value={"success": True})
    @patch("api.routers.auth.user_dao")
    def test_signup_success(self, mock_user_dao, mock_register, client):
        mock_user_dao.get_by_email.return_value = None
        resp = client.post("/auth/signup", json={
            "username": "newstudent",
            "password": "SecurePass1",
            "role": "student",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "grade": "10",
        })
        assert resp.status_code == 201
        assert "message" in resp.json()

    @pytest.mark.api
    @patch("api.routers.auth.user_dao")
    def test_signup_duplicate_email(self, mock_user_dao, client):
        mock_user_dao.get_by_email.return_value = {"user_id": "existing"}
        resp = client.post("/auth/signup", json={
            "username": "newstudent",
            "password": "SecurePass1",
            "role": "student",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "grade": "10",
        })
        assert resp.status_code == 409

    @pytest.mark.api
    @patch("api.routers.auth.user_dao")
    def test_signup_invalid_role(self, mock_user_dao, client):
        mock_user_dao.get_by_email.return_value = None
        resp = client.post("/auth/signup", json={
            "username": "hacker",
            "password": "SecurePass1",
            "role": "admin",
            "first_name": "Bad",
            "last_name": "Actor",
            "email": "bad@example.com",
        })
        assert resp.status_code == 400

    @pytest.mark.api
    @patch("api.routers.auth.user_dao")
    def test_signup_student_missing_grade(self, mock_user_dao, client):
        mock_user_dao.get_by_email.return_value = None
        resp = client.post("/auth/signup", json={
            "username": "nograde",
            "password": "SecurePass1",
            "role": "student",
            "first_name": "No",
            "last_name": "Grade",
            "email": "nograde@example.com",
        })
        assert resp.status_code == 400

    @pytest.mark.api
    @patch("api.routers.auth.register_user", return_value={"success": False, "error": "Username already exists"})
    @patch("api.routers.auth.user_dao")
    def test_signup_username_conflict(self, mock_user_dao, mock_register, client):
        mock_user_dao.get_by_email.return_value = None
        resp = client.post("/auth/signup", json={
            "username": "taken",
            "password": "SecurePass1",
            "role": "student",
            "first_name": "Dup",
            "last_name": "User",
            "email": "dup@example.com",
            "grade": "9",
        })
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

class TestLoginRoute:

    @pytest.mark.api
    @patch("api.routers.auth.student_dao")
    @patch("api.routers.auth.session_dao")
    @patch("api.routers.auth.authenticate_user", return_value=True)
    def test_login_success_returns_token(self, mock_auth, mock_session, mock_student, client):
        mock_student.get_student_by_id.return_value = {
            "strength": "math", "weakness": "reading",
            "interest": "science", "learning_style": "visual",
        }
        resp = client.post("/auth/login", json={
            "username": "stu1", "password": "SecurePass1", "role": "student"
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    @pytest.mark.api
    @patch("api.routers.auth.authenticate_user", return_value=False)
    def test_login_bad_credentials(self, mock_auth, client):
        resp = client.post("/auth/login", json={
            "username": "stu1", "password": "wrong", "role": "student"
        })
        assert resp.status_code == 401

    @pytest.mark.api
    @patch("api.routers.auth.student_dao")
    @patch("api.routers.auth.session_dao")
    @patch("api.routers.auth.authenticate_user", return_value=True)
    def test_login_incomplete_profile_sets_flag(self, mock_auth, mock_session, mock_student, client):
        mock_student.get_student_by_id.return_value = {
            "strength": None, "weakness": None, "interest": None, "learning_style": None,
        }
        resp = client.post("/auth/login", json={
            "username": "stu1", "password": "SecurePass1", "role": "student"
        })
        assert resp.status_code == 200
        assert resp.json().get("needs_profile") is True


# ---------------------------------------------------------------------------
# POST /auth/password-reset/request
# ---------------------------------------------------------------------------

class TestPasswordResetRequest:

    @pytest.mark.api
    @patch("api.routers.auth.password_reset_service")
    def test_reset_request_always_200(self, mock_svc, client):
        mock_svc.request_password_reset.return_value = {
            "success": True,
            "message": "If an account exists with that email, we sent a password reset link.",
        }
        resp = client.post("/auth/password-reset/request", json={"email": "anyone@example.com"})
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_reset_request_empty_email(self, client):
        resp = client.post("/auth/password-reset/request", json={"email": "   "})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /auth/password-reset/confirm
# ---------------------------------------------------------------------------

class TestPasswordResetConfirm:

    @pytest.mark.api
    @patch("api.routers.auth.password_reset_service")
    def test_reset_confirm_success(self, mock_svc, client):
        mock_svc.confirm_password_reset.return_value = (
            True, "Your password has been updated successfully."
        )
        resp = client.post("/auth/password-reset/confirm", json={
            "token": "validtoken123", "new_password": "NewSecure1"
        })
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    @patch("api.routers.auth.password_reset_service")
    def test_reset_confirm_invalid_token(self, mock_svc, client):
        mock_svc.confirm_password_reset.return_value = (
            False, "This link is invalid or expired."
        )
        resp = client.post("/auth/password-reset/confirm", json={
            "token": "badtoken", "new_password": "NewSecure1"
        })
        assert resp.status_code == 400

    @pytest.mark.api
    def test_reset_confirm_missing_token(self, client):
        resp = client.post("/auth/password-reset/confirm", json={
            "token": "   ", "new_password": "NewSecure1"
        })
        assert resp.status_code == 400
