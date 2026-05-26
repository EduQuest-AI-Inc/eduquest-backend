import pytest
from unittest.mock import patch, MagicMock
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
        mock_svc = MagicMock()
        mock_svc.get_periods_by_owner.return_value = [{
            "period_id": "p1", "name": "Math", "status": "approved",
            "processing_status": "ready", "owner_id": "parent-1",
            "is_summer_quest": False, "file_urls": [],
        }]
        with patch("routers.parent.PeriodManagementService", return_value=mock_svc):
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 200
        assert resp.json()["periods"][0]["period_id"] == "p1"
        assert resp.json()["periods"][0]["name"] == "Math"
        mock_svc.get_periods_by_owner.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_my_periods_empty_returns_empty_list(self, client):
        mock_svc = MagicMock()
        mock_svc.get_periods_by_owner.return_value = []
        with patch("routers.parent.PeriodManagementService", return_value=mock_svc):
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == []

    @pytest.mark.api
    def test_my_periods_service_error_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.get_periods_by_owner.side_effect = RuntimeError("db down")
        with patch("routers.parent.PeriodManagementService", return_value=mock_svc):
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 500


class TestGenerateInvite:

    @pytest.mark.api
    def test_generate_invite_returns_201(self, client):
        mock_ps = MagicMock()
        mock_ps.generate_invite.return_value = {
            "code": "ABCD1234", "expires_at": "2026-05-01T00:00:00+00:00"
        }
        with patch("routers.parent.ParentService", return_value=mock_ps):
            resp = client.post("/parent/generate-invite")
        assert resp.status_code == 201
        assert resp.json()["code"] == "ABCD1234"
        assert "expires_at" in resp.json()
        mock_ps.generate_invite.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_generate_invite_service_error_returns_500(self, client):
        mock_ps = MagicMock()
        mock_ps.generate_invite.side_effect = RuntimeError("fail")
        with patch("routers.parent.ParentService", return_value=mock_ps):
            resp = client.post("/parent/generate-invite")
        assert resp.status_code == 500


class TestGetStudents:

    @pytest.mark.api
    def test_get_students_returns_list(self, client):
        mock_ps = MagicMock()
        mock_ps.get_linked_students.return_value = [
            {"user_id": "s1", "first_name": "Alice", "last_name": "Smith",
             "grade": "10", "email": "alice@eduquestai.org"}
        ]
        with patch("routers.parent.ParentService", return_value=mock_ps):
            resp = client.get("/parent/students")
        assert resp.status_code == 200
        assert len(resp.json()["students"]) == 1
        mock_ps.get_linked_students.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_get_students_empty_returns_empty_list(self, client):
        mock_ps = MagicMock()
        mock_ps.get_linked_students.return_value = []
        with patch("routers.parent.ParentService", return_value=mock_ps):
            resp = client.get("/parent/students")
        assert resp.status_code == 200
        assert resp.json()["students"] == []

    @pytest.mark.api
    def test_get_students_service_error_returns_500(self, client):
        mock_ps = MagicMock()
        mock_ps.get_linked_students.side_effect = RuntimeError("fail")
        with patch("routers.parent.ParentService", return_value=mock_ps):
            resp = client.get("/parent/students")
        assert resp.status_code == 500


class TestEnrollStudent:

    @pytest.mark.api
    def test_enroll_student_success(self, client):
        mock_enrollment = MagicMock()
        mock_enrollment.validate_parent_enrollment_preconditions.return_value = None
        mock_enrollment.verify_period_id.return_value = {
            "period_id": "p1", "name": "Math", "status": "approved",
            "processing_status": "ready", "owner_id": "owner-1",
            "is_summer_quest": False, "file_urls": [],
        }

        with patch("routers.parent.EnrollmentService", return_value=mock_enrollment), \
             patch("routers.parent.check_owner_can_accept_student") as mock_owner_check:
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Student enrolled in class"
        assert body["period"]["period_id"] == "p1"
        mock_owner_check.assert_called_once_with("p1")

    @pytest.mark.api
    def test_enroll_student_not_linked_returns_400(self, client):
        from exceptions.validation_error import ValidationError as EQValidationError
        mock_enrollment = MagicMock()
        mock_enrollment.validate_parent_enrollment_preconditions.side_effect = EQValidationError(
            "Student is not linked to this parent account"
        )
        with patch("routers.parent.EnrollmentService", return_value=mock_enrollment):
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s-other", "period_id": "p1"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_enroll_student_already_enrolled_returns_400(self, client):
        from exceptions.validation_error import ValidationError as EQValidationError
        mock_enrollment = MagicMock()
        mock_enrollment.validate_parent_enrollment_preconditions.side_effect = EQValidationError(
            "Student is already enrolled in this class"
        )
        with patch("routers.parent.EnrollmentService", return_value=mock_enrollment):
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_enroll_student_owner_inactive_returns_403(self, client):
        from fastapi import HTTPException
        mock_enrollment = MagicMock()
        mock_enrollment.validate_parent_enrollment_preconditions.return_value = None
        owner_error = HTTPException(
            status_code=403,
            detail={
                "error": "This class is not currently accepting new students.",
                "code": "OWNER_MEMBERSHIP_INACTIVE",
            },
        )

        with patch("routers.parent.EnrollmentService", return_value=mock_enrollment), \
             patch("routers.parent.check_owner_can_accept_student", side_effect=owner_error):
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "OWNER_MEMBERSHIP_INACTIVE"

    @pytest.mark.api
    def test_enroll_student_plan_limit_returns_403(self, client):
        from fastapi import HTTPException
        mock_enrollment = MagicMock()
        mock_enrollment.validate_parent_enrollment_preconditions.return_value = None
        limit_error = HTTPException(
            status_code=403,
            detail={"error": "limit hit", "code": "PLAN_LIMIT_EXCEEDED"},
        )

        with patch("routers.parent.EnrollmentService", return_value=mock_enrollment), \
             patch("routers.parent.check_owner_can_accept_student", side_effect=limit_error):
            resp = client.post(
                "/parent/enroll-student",
                json={"student_id": "s1", "period_id": "p1"},
            )

        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "PLAN_LIMIT_EXCEEDED"
