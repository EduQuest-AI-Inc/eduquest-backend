import pytest
from data_access.student_dao import StudentDAO
from models.student import Student

_ID = "test-integration-student-dao"


def _student():
    return Student(
        user_id=_ID,
        first_name="Test",
        last_name="Student",
        email="test-integration-student@eduquestai.org",
        password="hashed",
        role="student",
        grade=10,
    )


@pytest.mark.integration
def test_add_and_get_student(supabase_required):
    dao = StudentDAO()
    try:
        dao.add_student(_student())
        result = dao.get_student_by_id(_ID)
        assert result is not None
        assert result["user_id"] == _ID
        assert result["grade"] == 10
    finally:
        dao.delete_student(_ID)


@pytest.mark.integration
def test_update_student_role_field(supabase_required):
    dao = StudentDAO()
    try:
        dao.add_student(_student())
        dao.update_student(_ID, {"grade": 11})
        result = dao.get_student_by_id(_ID)
        assert result["grade"] == 11
    finally:
        dao.delete_student(_ID)


@pytest.mark.integration
def test_update_tutorial_status(supabase_required):
    dao = StudentDAO()
    try:
        dao.add_student(_student())
        dao.update_tutorial_status(_ID, True)
        status = dao.get_tutorial_status(_ID)
        assert status is True
    finally:
        dao.delete_student(_ID)


@pytest.mark.integration
def test_update_canvas_credentials(supabase_required):
    dao = StudentDAO()
    try:
        dao.add_student(_student())
        dao.update_student(_ID, {"canvas_api_url": "https://canvas.example.com", "canvas_api_key": "key123"})
        result = dao.get_student_by_id(_ID)
        assert result["canvas_api_url"] == "https://canvas.example.com"
        # Clear credentials
        dao.update_student(_ID, {"canvas_api_url": None, "canvas_api_key": None})
        result2 = dao.get_student_by_id(_ID)
        assert result2["canvas_api_url"] is None
    finally:
        dao.delete_student(_ID)


@pytest.mark.integration
def test_delete_student(supabase_required):
    dao = StudentDAO()
    dao.add_student(_student())
    dao.delete_student(_ID)
    assert dao.get_student_by_id(_ID) is None
