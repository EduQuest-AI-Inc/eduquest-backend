import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload

OWNED_PERIOD = {"period_id": "p1", "owner_id": "teacher-1", "file_urls": []}
OTHER_PERIOD = {"period_id": "p1", "owner_id": "other-teacher", "file_urls": []}


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-1", role="teacher", token="fake-token"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestEnroll:

    @pytest.mark.api
    def test_enroll_success(self, client):
        with patch("routers.enrollment.service") as mock_svc:
            mock_svc.enroll_student.return_value = {"message": "Student teacher-1 enrolled in p1 successfully"}
            resp = client.post("/enrollment/enroll", json={"period_id": "p1", "semester": "Fall 2025"})
        assert resp.status_code == 200
        assert "message" in resp.json()
        mock_svc.enroll_student.assert_called_once_with("teacher-1", "p1", "Fall 2025")

    @pytest.mark.api
    def test_enroll_uses_default_semester(self, client):
        with patch("routers.enrollment.service") as mock_svc:
            mock_svc.enroll_student.return_value = {"message": "ok"}
            resp = client.post("/enrollment/enroll", json={"period_id": "p1"})
        assert resp.status_code == 200
        mock_svc.enroll_student.assert_called_once_with("teacher-1", "p1", "Fall 2025")

    @pytest.mark.api
    def test_enroll_missing_period_id_returns_422(self, client):
        resp = client.post("/enrollment/enroll", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_enroll_service_error_returns_500(self, client):
        with patch("routers.enrollment.service") as mock_svc:
            mock_svc.enroll_student.side_effect = RuntimeError("db error")
            resp = client.post("/enrollment/enroll", json={"period_id": "p1"})
        assert resp.status_code == 500


class TestGetEnrollments:

    @pytest.mark.api
    def test_get_enrollments_success(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd, \
             patch("routers.enrollment.service") as mock_svc:
            mock_pd.get_period_by_id.return_value = OWNED_PERIOD
            mock_svc.get_enrollments_for_period.return_value = {
                "students": [{"user_id": "s1"}], "file_urls": []
            }
            resp = client.get("/enrollment/enrollments/p1")
        assert resp.status_code == 200
        assert "students" in resp.json()
        assert len(resp.json()["students"]) == 1

    @pytest.mark.api
    def test_get_enrollments_period_not_found_returns_404(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd:
            mock_pd.get_period_by_id.return_value = None
            resp = client.get("/enrollment/enrollments/missing")
        assert resp.status_code == 404
        assert "Period not found" in resp.json()["detail"]

    @pytest.mark.api
    def test_get_enrollments_not_owner_returns_403(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd:
            mock_pd.get_period_by_id.return_value = OTHER_PERIOD
            resp = client.get("/enrollment/enrollments/p1")
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

    @pytest.mark.api
    def test_get_enrollments_service_error_returns_500(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd, \
             patch("routers.enrollment.service") as mock_svc:
            mock_pd.get_period_by_id.return_value = OWNED_PERIOD
            mock_svc.get_enrollments_for_period.side_effect = RuntimeError("crash")
            resp = client.get("/enrollment/enrollments/p1")
        assert resp.status_code == 500


class TestGetStudentProfile:

    @pytest.mark.api
    def test_get_student_profile_success(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd, \
             patch("routers.enrollment.service") as mock_svc:
            mock_pd.get_period_by_id.return_value = OWNED_PERIOD
            mock_svc.get_student_profile.return_value = {
                "interest": "math", "strength": "algebra",
                "weakness": "writing", "learning_style": "visual",
            }
            resp = client.get("/enrollment/student-profile/p1/s1")
        assert resp.status_code == 200
        assert resp.json()["interest"] == "math"

    @pytest.mark.api
    def test_get_student_profile_period_not_found_returns_404(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd:
            mock_pd.get_period_by_id.return_value = None
            resp = client.get("/enrollment/student-profile/missing/s1")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_get_student_profile_not_owner_returns_403(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd:
            mock_pd.get_period_by_id.return_value = OTHER_PERIOD
            resp = client.get("/enrollment/student-profile/p1/s1")
        assert resp.status_code == 403

    @pytest.mark.api
    def test_get_student_profile_not_found_returns_404(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd, \
             patch("routers.enrollment.service") as mock_svc:
            mock_pd.get_period_by_id.return_value = OWNED_PERIOD
            mock_svc.get_student_profile.return_value = None
            resp = client.get("/enrollment/student-profile/p1/s1")
        assert resp.status_code == 404
        assert "Profile not found" in resp.json()["detail"]

    @pytest.mark.api
    def test_get_student_profile_service_error_returns_500(self, client):
        with patch("routers.enrollment._period_dao") as mock_pd, \
             patch("routers.enrollment.service") as mock_svc:
            mock_pd.get_period_by_id.return_value = OWNED_PERIOD
            mock_svc.get_student_profile.side_effect = RuntimeError("crash")
            resp = client.get("/enrollment/student-profile/p1/s1")
        assert resp.status_code == 500
