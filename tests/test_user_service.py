import pytest
from unittest.mock import MagicMock

from routes.user.user_service import UserService


def _svc():
    svc = UserService.__new__(UserService)
    svc.session_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.teacher_dao = MagicMock()
    # UserService has no parent_dao; only session/student/teacher
    return svc


@pytest.mark.unit
def test_get_user_profile_invalid_token():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = []

    with pytest.raises(ValueError):
        svc.get_user_profile("bad-token")


@pytest.mark.unit
def test_get_user_profile_student():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = [
        {"user_id": "u1", "role": "student"}
    ]
    svc.student_dao.get_student_by_id.return_value = {"user_id": "u1", "first_name": "Alice"}

    result = svc.get_user_profile("token123")

    svc.student_dao.get_student_by_id.assert_called_once_with("u1")
    assert result["role"] == "student"


@pytest.mark.unit
def test_get_user_profile_teacher():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = [
        {"user_id": "t1", "role": "teacher"}
    ]
    svc.teacher_dao.get_teacher_by_id.return_value = {"user_id": "t1", "first_name": "Bob"}

    result = svc.get_user_profile("token456")

    svc.teacher_dao.get_teacher_by_id.assert_called_once_with("t1")
    assert result["role"] == "teacher"


@pytest.mark.unit
def test_get_user_profile_unrecognized_role():
    svc = _svc()
    svc.session_dao.get_sessions_by_auth_token.return_value = [
        {"user_id": "x1", "role": "admin"}
    ]

    with pytest.raises(ValueError):
        svc.get_user_profile("token789")


@pytest.mark.unit
def test_update_tutorial_status():
    svc = _svc()

    svc.update_tutorial_status("u1", True)

    svc.student_dao.update_tutorial_status.assert_called_once_with("u1", True)


@pytest.mark.unit
def test_get_tutorial_status():
    svc = _svc()
    svc.student_dao.get_tutorial_status.return_value = True

    result = svc.get_tutorial_status("u1")

    svc.student_dao.get_tutorial_status.assert_called_once_with("u1")
    assert result is True
