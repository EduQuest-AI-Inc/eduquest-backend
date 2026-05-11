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
        with patch("routers.lessons._lesson_pptx_dao") as mock_pptx_dao, \
             patch("routers.lessons._lesson_dao") as mock_lesson_dao, \
             patch("routers.lessons._period_dao") as mock_period_dao, \
             patch("routers.lessons.s3_service") as mock_s3:
            mock_pptx_dao.get_latest_done.return_value = _DONE_ROW
            mock_lesson_dao.get_by_lesson_id.return_value = _LESSON_ROW
            mock_period_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_s3.generate_presigned_url.return_value = _PRESIGNED_URL

            resp = teacher_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 200
        body = resp.json()
        assert body["url"] == _PRESIGNED_URL
        assert body["expires_in"] == 900
        assert body["lesson_name"] == "Algebra Basics"

    @pytest.mark.api
    def test_student_can_download(self, student_client):
        mock_enrollment = MagicMock()
        mock_enrollment.check_enrolled.return_value = None

        with patch("routers.lessons._lesson_pptx_dao") as mock_pptx_dao, \
             patch("routers.lessons._lesson_dao") as mock_lesson_dao, \
             patch("routers.lessons._enrollment_service", mock_enrollment), \
             patch("routers.lessons.s3_service") as mock_s3:
            mock_pptx_dao.get_latest_done.return_value = _DONE_ROW
            mock_lesson_dao.get_by_lesson_id.return_value = _LESSON_ROW
            mock_s3.generate_presigned_url.return_value = _PRESIGNED_URL

            resp = student_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 200
        assert resp.json()["url"] == _PRESIGNED_URL

    @pytest.mark.api
    def test_student_not_enrolled_forbidden(self, student_client):
        mock_enrollment = MagicMock()
        mock_enrollment.check_enrolled.side_effect = ValidationError("not enrolled")

        with patch("routers.lessons._lesson_pptx_dao") as mock_pptx_dao, \
             patch("routers.lessons._enrollment_service", mock_enrollment):
            mock_pptx_dao.get_latest_done.return_value = _DONE_ROW

            resp = student_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 403

    @pytest.mark.api
    def test_non_owner_teacher_forbidden(self, other_teacher_client):
        with patch("routers.lessons._lesson_pptx_dao") as mock_pptx_dao, \
             patch("routers.lessons._period_dao") as mock_period_dao:
            mock_pptx_dao.get_latest_done.return_value = _DONE_ROW
            mock_period_dao.get_period_by_id.return_value = _OWNED_PERIOD  # owner_id = teacher-1, not other-teacher

            resp = other_teacher_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 403

    @pytest.mark.api
    def test_no_completed_pptx_not_found(self, teacher_client):
        with patch("routers.lessons._lesson_pptx_dao") as mock_pptx_dao:
            mock_pptx_dao.get_latest_done.return_value = None

            resp = teacher_client.get(f"/lessons/{_LESSON_ID}/pptx")

        assert resp.status_code == 404
