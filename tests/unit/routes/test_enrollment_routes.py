import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload, Role


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="user-1", role=Role.STUDENT, token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestMyPeriods:

    @pytest.mark.api
    def test_my_periods_returns_list(self, client):
        with patch("routers.enrollment.service") as mock_ps:
            mock_ps.get_my_periods.return_value = [{"period_id": "p1"}]
            resp = client.get("/enrollment/my-periods")
        assert resp.status_code == 200
        mock_ps.get_my_periods.assert_called_once_with("user-1")

    @pytest.mark.api
    def test_my_periods_empty_returns_empty_list(self, client):
        with patch("routers.enrollment.service") as mock_ps:
            mock_ps.get_my_periods.return_value = []
            resp = client.get("/enrollment/my-periods")
        assert resp.status_code == 200
        assert resp.json() == []


class TestVerifyPeriod:

    @pytest.mark.api
    def test_verify_period_success(self, client):
        with patch("routers.enrollment._period_management_svc") as mock_pd, \
             patch("routers.enrollment.service") as mock_ps:
            mock_pd.get_period_by_id.return_value = None  # skip owner membership check
            mock_ps.verify_period_id.return_value = {"period_id": "p1", "name": "Math"}
            resp = client.post("/enrollment/verify-period", json={"period_id": "p1"})
        assert resp.status_code == 200
        assert resp.json()["period"]["period_id"] == "p1"
        assert "message" in resp.json()


class TestUnenroll:

    @pytest.mark.api
    def test_unenroll_success(self, client):
        with patch("routers.enrollment.service") as mock_ps:
            mock_ps.unenroll_from_period.return_value = {"message": "Unenrolled", "period_id": "p1"}
            resp = client.post("/enrollment/unenroll", json={"period_id": "p1"})
        assert resp.status_code == 200
        assert resp.json()["period_id"] == "p1"

    @pytest.mark.api
    def test_unenroll_missing_period_id_returns_422(self, client):
        resp = client.post("/enrollment/unenroll", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_unenroll_not_enrolled_returns_400(self, client):
        with patch("routers.enrollment.service") as mock_ps:
            from exceptions.validation_error import ValidationError
            mock_ps.unenroll_from_period.side_effect = ValidationError("You are not enrolled in period X")
            resp = client.post("/enrollment/unenroll", json={"period_id": "X"})
        assert resp.status_code == 400


class TestAcceptParentInvite:

    @pytest.mark.api
    def test_accept_invite_success(self, client):
        with patch("routers.enrollment.parent_service") as mock_parent:
            mock_parent.accept_invite.return_value = {
                "message": "Successfully linked", "student_id": "user-1", "parent_id": "parent-1"
            }
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 200
        mock_parent.accept_invite.assert_called_once_with("user-1", "ABCD1234")

    @pytest.mark.api
    def test_accept_invite_empty_code_returns_400(self, client):
        resp = client.post("/enrollment/accept-parent-invite", json={"code": "   "})
        assert resp.status_code == 400
        assert "detail" in resp.json()

    @pytest.mark.api
    def test_accept_invite_expired_returns_410(self, client):
        with patch("routers.enrollment.parent_service") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Invite code has expired")
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 410

    @pytest.mark.api
    def test_accept_invite_already_used_returns_410(self, client):
        with patch("routers.enrollment.parent_service") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Invite code has already been used")
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 410

    @pytest.mark.api
    def test_accept_invite_invalid_code_returns_404(self, client):
        with patch("routers.enrollment.parent_service") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Invalid invite code")
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_accept_invite_other_value_error_returns_400(self, client):
        with patch("routers.enrollment.parent_service") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Something else went wrong")
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_accept_invite_exception_returns_500(self, client):
        with patch("routers.enrollment.parent_service") as mock_parent:
            mock_parent.accept_invite.side_effect = RuntimeError("crash")
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 500
