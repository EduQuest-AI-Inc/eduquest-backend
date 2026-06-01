import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload, Role
from exceptions.validation_error import ValidationError

_LESSON_ID = "lesson-uuid-1"
_PERIOD_ID = "period-1"
_OWNER_ID = "teacher-1"
_STUDENT_ID = "student-1"
_S3_KEY = f"pptx/{_PERIOD_ID}/{_LESSON_ID}.pptx"
_PRESIGNED_URL = "https://s3.amazonaws.com/bucket/pptx/mock-url?sig=abc"

_DONE_ROW = {
    "pptx_id": "pptx-uuid-1",
    "lesson_id": _LESSON_ID,
    "period_id": _PERIOD_ID,
    "status": "done",
    "s3_key": _S3_KEY,
}
_LESSON_ROW = {"lesson_id": _LESSON_ID, "lesson_name": "Algebra Basics"}
_OWNED_PERIOD = {"period_id": _PERIOD_ID, "owner_id": _OWNER_ID}


@pytest.fixture
def teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub=_OWNER_ID, role=Role.TEACHER, token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def student_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub=_STUDENT_ID, role=Role.STUDENT, token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="other-teacher", role=Role.TEACHER, token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetLessonPptx:

    @pytest.mark.api
    def test_teacher_can_download(self, teacher_client):
        mock_ls = MagicMock()
        mock_ls.get_latest_done_pptx.return_value = _DONE_ROW
        mock_ls.get_lesson_by_id.return_value = _LESSON_ROW
        mock_period_svc = MagicMock()
        mock_period_svc.get_period_by_id.return_value = _OWNED_PERIOD
        with patch("routers.lessons.LessonsService", return_value=mock_ls), \
             patch("routers.lessons.PeriodManagementService", return_value=mock_period_svc), \
             patch("routers.lessons.s3_service") as mock_s3:
            mock_s3.generate_presigned_url.return_value = _PRESIGNED_URL
            resp = teacher_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 200
        body = resp.json()
        assert body["url"] == _PRESIGNED_URL
        assert body["expires_in"] == 900
        assert body["lesson_name"] == "Algebra Basics"

    @pytest.mark.api
    def test_student_can_download(self, student_client):
        mock_ls = MagicMock()
        mock_ls.get_latest_done_pptx.return_value = _DONE_ROW
        mock_ls.get_lesson_by_id.return_value = _LESSON_ROW
        mock_enrollment = MagicMock()
        mock_enrollment.check_enrolled.return_value = None
        with patch("routers.lessons.LessonsService", return_value=mock_ls), \
             patch("routers.lessons.EnrollmentService", return_value=mock_enrollment), \
             patch("routers.lessons.s3_service") as mock_s3:
            mock_s3.generate_presigned_url.return_value = _PRESIGNED_URL
            resp = student_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 200
        assert resp.json()["url"] == _PRESIGNED_URL

    @pytest.mark.api
    def test_student_not_enrolled_forbidden(self, student_client):
        mock_ls = MagicMock()
        mock_ls.get_latest_done_pptx.return_value = _DONE_ROW
        mock_enrollment = MagicMock()
        mock_enrollment.check_enrolled.side_effect = ValidationError("not enrolled")
        with patch("routers.lessons.LessonsService", return_value=mock_ls), \
             patch("routers.lessons.EnrollmentService", return_value=mock_enrollment):
            resp = student_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 403

    @pytest.mark.api
    def test_non_owner_teacher_forbidden(self, other_teacher_client):
        mock_ls = MagicMock()
        mock_ls.get_latest_done_pptx.return_value = _DONE_ROW
        mock_period_svc = MagicMock()
        mock_period_svc.get_period_by_id.return_value = _OWNED_PERIOD  # owner_id = teacher-1, not other-teacher
        with patch("routers.lessons.LessonsService", return_value=mock_ls), \
             patch("routers.lessons.PeriodManagementService", return_value=mock_period_svc):
            resp = other_teacher_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 403

    @pytest.mark.api
    def test_no_completed_pptx_not_found(self, teacher_client):
        mock_ls = MagicMock()
        mock_ls.get_latest_done_pptx.return_value = None
        with patch("routers.lessons.LessonsService", return_value=mock_ls):
            resp = teacher_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 404


class TestRegenerateLessonPptx:

    @pytest.mark.api
    def test_regenerate_returns_503_when_pptx_disabled(self, teacher_client, monkeypatch):
        monkeypatch.setenv("PPTX_GENERATION_ENABLED", "false")
        _PENDING_ROW = {**_DONE_ROW, "status": "pending"}
        mock_ls = MagicMock()
        mock_ls.get_pptx_by_lesson_id.return_value = _PENDING_ROW
        mock_ls.get_latest_done_pptx.return_value = None
        mock_period_svc = MagicMock()
        mock_period_svc.get_period_by_id.return_value = _OWNED_PERIOD
        with patch("routers.lessons.LessonsService", return_value=mock_ls), \
             patch("routers.lessons.PeriodManagementService", return_value=mock_period_svc):
            resp = teacher_client.post(f"/lessons/{_LESSON_ID}/pptx/regenerate")

        assert resp.status_code == 503
        assert "disabled" in resp.json()["detail"].lower()
