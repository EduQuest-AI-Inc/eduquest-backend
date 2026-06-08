import pytest
from unittest.mock import MagicMock, patch
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
        mock_svc = MagicMock()
        mock_svc.get_my_periods.return_value = [{"period_id": "p1", "name": "Math", "is_summer_quest": False, "file_urls": []}]
        with patch("routers.enrollment.EnrollmentService", return_value=mock_svc):
            resp = client.get("/enrollment/my-periods")
        assert resp.status_code == 200
        mock_svc.get_my_periods.assert_called_once_with("user-1")

    @pytest.mark.api
    def test_my_periods_empty_returns_empty_list(self, client):
        mock_svc = MagicMock()
        mock_svc.get_my_periods.return_value = []
        with patch("routers.enrollment.EnrollmentService", return_value=mock_svc):
            resp = client.get("/enrollment/my-periods")
        assert resp.status_code == 200
        assert resp.json() == []


class TestVerifyPeriod:

    @pytest.mark.api
    def test_verify_period_success(self, client):
        mock_enrollment_svc = MagicMock()
        mock_enrollment_svc.verify_period_id.return_value = {
            "period_id": "p1", "name": "Math", "status": "approved",
            "processing_status": "ready", "owner_id": "teacher-1",
            "is_summer_quest": False, "file_urls": [],
        }
        with patch("routers.enrollment.check_owner_can_accept_student") as mock_owner_check, \
             patch("routers.enrollment.EnrollmentService", return_value=mock_enrollment_svc):
            resp = client.post("/enrollment/verify-period", json={"period_id": "p1"})
        assert resp.status_code == 200
        assert resp.json()["period"]["period_id"] == "p1"
        assert "message" in resp.json()
        mock_owner_check.assert_called_once_with("p1")

    @pytest.mark.api
    def test_verify_period_owner_check_uses_admin_period_data(self, client):
        mock_access_svc = MagicMock()
        mock_access_svc.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "owner-1"}
        mock_user_svc = MagicMock()
        mock_user_svc.get_by_id.return_value = {"role": "parent"}
        mock_membership = MagicMock()
        mock_membership.check_can_add_student_to_period.return_value = None
        mock_enrollment_svc = MagicMock()
        mock_enrollment_svc.verify_period_id.return_value = {
            "period_id": "p1", "name": "Math", "status": "approved",
            "processing_status": "ready", "owner_id": "owner-1",
            "is_summer_quest": False, "file_urls": [],
        }

        with patch("routers.enrollment_access.EnrollmentService", return_value=mock_access_svc) as access_svc_cls, \
             patch("routers.enrollment_access.UserService", return_value=mock_user_svc), \
             patch("routers.enrollment_access.MembershipService", return_value=mock_membership), \
             patch("routers.enrollment.EnrollmentService", return_value=mock_enrollment_svc):
            resp = client.post("/enrollment/verify-period", json={"period_id": "p1"})

        assert resp.status_code == 200
        access_svc_cls.assert_called_once_with()
        mock_access_svc.get_period_by_id.assert_called_once_with("p1")
        mock_membership.check_can_add_student_to_period.assert_called_once_with(
            "owner-1", "parent", "p1"
        )

    @pytest.mark.api
    def test_verify_period_owner_inactive_returns_403(self, client):
        from services.billing.membership_service import MembershipRequiredError
        mock_access_svc = MagicMock()
        mock_access_svc.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "owner-1"}
        mock_user_svc = MagicMock()
        mock_user_svc.get_by_id.return_value = {"role": "teacher"}
        mock_membership = MagicMock()
        mock_membership.check_can_add_student_to_period.side_effect = MembershipRequiredError(MagicMock())

        with patch("routers.enrollment_access.EnrollmentService", return_value=mock_access_svc), \
             patch("routers.enrollment_access.UserService", return_value=mock_user_svc), \
             patch("routers.enrollment_access.MembershipService", return_value=mock_membership):
            resp = client.post("/enrollment/verify-period", json={"period_id": "p1"})

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "OWNER_MEMBERSHIP_INACTIVE"

    @pytest.mark.api
    def test_verify_period_plan_limit_returns_403(self, client):
        from services.billing.membership_service import PlanLimitExceededError
        mock_access_svc = MagicMock()
        mock_access_svc.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "owner-1"}
        mock_user_svc = MagicMock()
        mock_user_svc.get_by_id.return_value = {"role": "teacher"}
        mock_membership = MagicMock()
        mock_membership.check_can_add_student_to_period.side_effect = PlanLimitExceededError("limit hit")

        with patch("routers.enrollment_access.EnrollmentService", return_value=mock_access_svc), \
             patch("routers.enrollment_access.UserService", return_value=mock_user_svc), \
             patch("routers.enrollment_access.MembershipService", return_value=mock_membership):
            resp = client.post("/enrollment/verify-period", json={"period_id": "p1"})

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "PLAN_LIMIT_EXCEEDED"


class TestUnenroll:

    @pytest.mark.api
    def test_unenroll_success(self, client):
        mock_svc = MagicMock()
        mock_svc.unenroll_from_period.return_value = {"message": "Unenrolled", "period_id": "p1"}
        with patch("routers.enrollment.EnrollmentService", return_value=mock_svc):
            resp = client.post("/enrollment/unenroll", json={"period_id": "p1"})
        assert resp.status_code == 200
        assert resp.json()["period_id"] == "p1"

    @pytest.mark.api
    def test_unenroll_missing_period_id_returns_422(self, client):
        resp = client.post("/enrollment/unenroll", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_unenroll_not_enrolled_returns_400(self, client):
        mock_svc = MagicMock()
        from exceptions.validation_error import ValidationError
        mock_svc.unenroll_from_period.side_effect = ValidationError("You are not enrolled in period X")
        with patch("routers.enrollment.EnrollmentService", return_value=mock_svc):
            resp = client.post("/enrollment/unenroll", json={"period_id": "X"})
        assert resp.status_code == 400


class TestAcceptParentInvite:

    @pytest.mark.api
    def test_accept_invite_success(self, client):
        mock_parent = MagicMock()
        mock_parent.accept_invite.return_value = {
            "message": "Successfully linked", "student_id": "user-1", "parent_id": "parent-1"
        }
        with patch("routers.enrollment.ParentService", return_value=mock_parent):
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
        mock_parent = MagicMock()
        mock_parent.accept_invite.side_effect = ValueError("Invite code has expired")
        with patch("routers.enrollment.ParentService", return_value=mock_parent):
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 410

    @pytest.mark.api
    def test_accept_invite_already_used_returns_410(self, client):
        mock_parent = MagicMock()
        mock_parent.accept_invite.side_effect = ValueError("Invite code has already been used")
        with patch("routers.enrollment.ParentService", return_value=mock_parent):
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 410

    @pytest.mark.api
    def test_accept_invite_invalid_code_returns_404(self, client):
        mock_parent = MagicMock()
        mock_parent.accept_invite.side_effect = ValueError("Invalid invite code")
        with patch("routers.enrollment.ParentService", return_value=mock_parent):
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_accept_invite_other_value_error_returns_400(self, client):
        mock_parent = MagicMock()
        mock_parent.accept_invite.side_effect = ValueError("Something else went wrong")
        with patch("routers.enrollment.ParentService", return_value=mock_parent):
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_accept_invite_exception_returns_500(self, client):
        mock_parent = MagicMock()
        mock_parent.accept_invite.side_effect = RuntimeError("crash")
        with patch("routers.enrollment.ParentService", return_value=mock_parent):
            resp = client.post("/enrollment/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 500
