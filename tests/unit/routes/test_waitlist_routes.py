import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from exceptions.not_found_error import NotFoundError
from main import app
from routers.deps import get_auth, AuthPayload


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-1", role="teacher", token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetWaitlistStatus:

    @pytest.mark.api
    def test_get_status_success(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.get_status.return_value = {"on_waitlist": True, "position": 5, "status": "pending"}
            resp = client.get("/pilot-waitlist/status")
        assert resp.status_code == 200
        assert resp.json()["on_waitlist"] is True
        mock_svc.get_status.assert_called_once_with("teacher-1")

    @pytest.mark.api
    def test_get_status_exception_returns_500(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.get_status.side_effect = RuntimeError("db down")
            resp = client.get("/pilot-waitlist/status")
        assert resp.status_code == 500
        assert resp.json()["error"] == "Internal server error"


class TestJoinWaitlist:

    @pytest.mark.api
    def test_join_no_referral_code_success(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.join.return_value = {"success": True, "position": 10, "referral_code": "CODE1234"}
            resp = client.post("/pilot-waitlist/join", json={})
        assert resp.status_code == 200
        mock_svc.join.assert_called_once_with("teacher-1", None)

    @pytest.mark.api
    def test_join_with_referral_code_field(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.join.return_value = {"success": True}
            resp = client.post("/pilot-waitlist/join", json={"referral_code": "REF99"})
        assert resp.status_code == 200
        mock_svc.join.assert_called_once_with("teacher-1", "REF99")

    @pytest.mark.api
    def test_join_with_referralCode_camel_case_field(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.join.return_value = {"success": True}
            resp = client.post("/pilot-waitlist/join", json={"referralCode": "REF88"})
        assert resp.status_code == 200
        mock_svc.join.assert_called_once_with("teacher-1", "REF88")

    @pytest.mark.api
    def test_join_referralCode_takes_priority_over_referral_code(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.join.return_value = {"success": True}
            resp = client.post(
                "/pilot-waitlist/join",
                json={"referralCode": "FIRST", "referral_code": "SECOND"},
            )
        assert resp.status_code == 200
        mock_svc.join.assert_called_once_with("teacher-1", "FIRST")

    @pytest.mark.api
    def test_join_teacher_not_found_returns_404(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.join.side_effect = NotFoundError("Teacher not found")
            resp = client.post("/pilot-waitlist/join", json={})
        assert resp.status_code == 404
        assert "Teacher not found" in resp.json()["error"]

    @pytest.mark.api
    def test_join_exception_returns_500(self, client):
        with patch("routers.waitlist.svc") as mock_svc:
            mock_svc.join.side_effect = RuntimeError("crash")
            resp = client.post("/pilot-waitlist/join", json={})
        assert resp.status_code == 500
        assert resp.json()["error"] == "Internal server error"


class TestApproveTeacher:
    # teacher-1 is the sub used by the module fixture; patch ADMIN_IDS so it passes the admin check.

    @pytest.mark.api
    def test_approve_success(self, client):
        with patch("routers.waitlist.ADMIN_IDS", {"teacher-1"}), \
             patch("routers.waitlist.svc") as mock_svc:
            mock_svc.approve.return_value = {
                "success": True, "waitlist_updated": True, "teacher_updated": True
            }
            resp = client.post("/pilot-waitlist/approve/target-teacher")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_svc.approve.assert_called_once_with("target-teacher")

    @pytest.mark.api
    def test_approve_service_returns_failure_returns_400(self, client):
        with patch("routers.waitlist.ADMIN_IDS", {"teacher-1"}), \
             patch("routers.waitlist.svc") as mock_svc:
            mock_svc.approve.return_value = {
                "success": False, "waitlist_updated": False, "teacher_updated": False
            }
            resp = client.post("/pilot-waitlist/approve/target-teacher")
        assert resp.status_code == 400
        assert "Failed to approve teacher" in resp.json()["detail"]

    @pytest.mark.api
    def test_approve_exception_returns_500(self, client):
        with patch("routers.waitlist.ADMIN_IDS", {"teacher-1"}), \
             patch("routers.waitlist.svc") as mock_svc:
            mock_svc.approve.side_effect = RuntimeError("crash")
            resp = client.post("/pilot-waitlist/approve/target-teacher")
        assert resp.status_code == 500
        assert resp.json()["error"] == "Internal server error"

    @pytest.mark.api
    def test_approve_uses_path_param_user_id(self, client):
        with patch("routers.waitlist.ADMIN_IDS", {"teacher-1"}), \
             patch("routers.waitlist.svc") as mock_svc:
            mock_svc.approve.return_value = {"success": True, "waitlist_updated": True, "teacher_updated": True}
            resp = client.post("/pilot-waitlist/approve/completely-different-user")
        assert resp.status_code == 200
        mock_svc.approve.assert_called_once_with("completely-different-user")
