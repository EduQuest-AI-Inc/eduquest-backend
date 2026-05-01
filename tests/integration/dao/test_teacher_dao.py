import pytest
from data_access.teacher_dao import TeacherDAO
from models.teacher import Teacher

_ID = "test-integration-teacher-dao"


def _teacher():
    return Teacher(
        user_id=_ID,
        first_name="Test",
        last_name="Teacher",
        email="test-integration-teacher@eduquestai.org",
        password="hashed",
        role="teacher",
        pilot_approved=False,
    )


@pytest.mark.integration
def test_add_and_get_teacher(supabase_required):
    dao = TeacherDAO()
    try:
        dao.add_teacher(_teacher())
        result = dao.get_teacher_by_id(_ID)
        assert result is not None
        assert result["user_id"] == _ID
        assert result["pilot_approved"] is False
    finally:
        dao.delete_teacher(_ID)


@pytest.mark.integration
def test_update_teacher(supabase_required):
    dao = TeacherDAO()
    try:
        dao.add_teacher(_teacher())
        dao.update_teacher(_ID, {"pilot_approved": True})
        result = dao.get_teacher_by_id(_ID)
        assert result["pilot_approved"] is True
    finally:
        dao.delete_teacher(_ID)


@pytest.mark.integration
def test_update_canvas_credentials(supabase_required):
    dao = TeacherDAO()
    try:
        dao.add_teacher(_teacher())
        dao.update_canvas_credentials(_ID, "https://canvas.example.com", "key123")
        result = dao.get_teacher_by_id(_ID)
        assert result["canvas_api_url"] == "https://canvas.example.com"
        assert result["canvas_api_key"] == "key123"
        dao.clear_canvas_credentials(_ID)
        result2 = dao.get_teacher_by_id(_ID)
        assert result2["canvas_api_url"] is None
        assert result2["canvas_api_key"] is None
    finally:
        dao.delete_teacher(_ID)


@pytest.mark.integration
def test_delete_teacher(supabase_required):
    dao = TeacherDAO()
    dao.add_teacher(_teacher())
    dao.delete_teacher(_ID)
    assert dao.get_teacher_by_id(_ID) is None
