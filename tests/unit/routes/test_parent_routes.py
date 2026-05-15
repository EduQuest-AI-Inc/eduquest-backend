import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, require_active_membership, AuthPayload, Role

_PARENT_AUTH = AuthPayload(sub="parent-1", role=Role.PARENT, token="fake-token")


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = lambda: _PARENT_AUTH
    app.dependency_overrides[require_active_membership] = lambda: _PARENT_AUTH
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestMyPeriods:

    @pytest.mark.api
    def test_my_periods_returns_list(self, client):
        with patch("routers.parent.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.return_value = [{"period_id": "p1", "name": "Math"}]
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == [{"period_id": "p1", "name": "Math"}]
        mock_pms.get_periods_by_owner.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_my_periods_empty_returns_empty_list(self, client):
        with patch("routers.parent.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.return_value = []
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == []

    @pytest.mark.api
    def test_my_periods_service_error_returns_500(self, client):
        with patch("routers.parent.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.side_effect = RuntimeError("db down")
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 500


class TestGenerateInvite:

    @pytest.mark.api
    def test_generate_invite_returns_201(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.generate_invite.return_value = {
                "code": "ABCD1234", "expires_at": "2026-05-01T00:00:00+00:00"
            }
            resp = client.post("/parent/generate-invite")
        assert resp.status_code == 201
        assert resp.json()["code"] == "ABCD1234"
        assert "expires_at" in resp.json()
        mock_ps.generate_invite.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_generate_invite_service_error_returns_500(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.generate_invite.side_effect = RuntimeError("fail")
            resp = client.post("/parent/generate-invite")
        assert resp.status_code == 500


class TestGetStudents:

    @pytest.mark.api
    def test_get_students_returns_list(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.get_linked_students.return_value = [
                {"user_id": "s1", "first_name": "Alice", "last_name": "Smith",
                 "grade": "10", "email": "alice@eduquestai.org"}
            ]
            resp = client.get("/parent/students")
        assert resp.status_code == 200
        assert len(resp.json()["students"]) == 1
        mock_ps.get_linked_students.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_get_students_empty_returns_empty_list(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.get_linked_students.return_value = []
            resp = client.get("/parent/students")
        assert resp.status_code == 200
        assert resp.json()["students"] == []

    @pytest.mark.api
    def test_get_students_service_error_returns_500(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.get_linked_students.side_effect = RuntimeError("fail")
            resp = client.get("/parent/students")
        assert resp.status_code == 500


class TestEnrollStudent:

    @pytest.mark.api
    def test_enroll_student_success(self, client):
        with (
            patch("routers.parent.enrollment_service") as mock_es,
            patch("routers.parent.period_management_service") as mock_pms,
            patch("routers.parent.user_service") as mock_us,
            patch("routers.parent.membership_service") as mock_ms,
        ):
            mock_es.validate_parent_enrollment_preconditions.return_value = None
            mock_pms.get_period_by_id.return_value = {"owner_id": "owner-1", "name": "Math"}
            mock_us.get_by_id.return_value = {"role": "parent"}
            mock_ms.check_can_add_student_to_period.return_value = None
            mock_es.verify_period_id.return_value = {"period_id": "p1", "name": "Math"}

            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Student enrolled in class"
        assert body["period"]["period_id"] == "p1"

    @pytest.mark.api
    def test_enroll_student_not_linked_returns_400(self, client):
        from exceptions.validation_error import ValidationError as EQValidationError
        with patch("routers.parent.enrollment_service") as mock_es:
            mock_es.validate_parent_enrollment_preconditions.side_effect = EQValidationError(
                "Student is not linked to this parent account"
            )
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s-other", "period_id": "p1"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_enroll_student_already_enrolled_returns_400(self, client):
        from exceptions.validation_error import ValidationError as EQValidationError
        with patch("routers.parent.enrollment_service") as mock_es:
            mock_es.validate_parent_enrollment_preconditions.side_effect = EQValidationError(
                "Student is already enrolled in this class"
            )
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_enroll_student_owner_inactive_returns_403(self, client):
        from services.billing.membership_service import MembershipRequiredError
        with (
            patch("routers.parent.enrollment_service") as mock_es,
            patch("routers.parent.period_management_service") as mock_pms,
            patch("routers.parent.user_service") as mock_us,
            patch("routers.parent.membership_service") as mock_ms,
        ):
            mock_es.validate_parent_enrollment_preconditions.return_value = None
            mock_pms.get_period_by_id.return_value = {"owner_id": "owner-1"}
            mock_us.get_by_id.return_value = {"role": "teacher"}
            mock_ms.check_can_add_student_to_period.side_effect = MembershipRequiredError("inactive")

            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "OWNER_MEMBERSHIP_INACTIVE"

    @pytest.mark.api
    def test_enroll_student_plan_limit_returns_403(self, client):
        from services.billing.membership_service import PlanLimitExceededError
        with (
            patch("routers.parent.enrollment_service") as mock_es,
            patch("routers.parent.period_management_service") as mock_pms,
            patch("routers.parent.user_service") as mock_us,
            patch("routers.parent.membership_service") as mock_ms,
        ):
            mock_es.validate_parent_enrollment_preconditions.return_value = None
            mock_pms.get_period_by_id.return_value = {"owner_id": "owner-1"}
            mock_us.get_by_id.return_value = {"role": "teacher"}
            mock_ms.check_can_add_student_to_period.side_effect = PlanLimitExceededError("limit hit")

            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "PLAN_LIMIT_EXCEEDED"
