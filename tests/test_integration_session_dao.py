"""
Integration tests for SessionDAO.
Uses UserDAO to create the prerequisite user row.
"""
import pytest
from data_access.session_dao import SessionDAO
from data_access.user_dao import UserDAO
from models.session import Session

_TOKEN = "test-integration-session-token"
_USER_ID = "test-integration-session-user"


def _setup(user_dao):
    user_dao._insert({
        "user_id": _USER_ID, "first_name": "S", "last_name": "User",
        "email": "test-integration-session@example.com", "password": "pw", "role": "student",
    })


def _teardown(dao, user_dao):
    try:
        dao.delete_session(_TOKEN)
    except Exception:
        pass
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_add_and_get_session(supabase_required):
    dao = SessionDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        session = Session(auth_token=_TOKEN, user_id=_USER_ID, role="student")
        dao.add_session(session)
        results = dao.get_sessions_by_auth_token(_TOKEN)
        assert len(results) == 1
        assert results[0]["user_id"] == _USER_ID
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_update_session(supabase_required):
    dao = SessionDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        session = Session(auth_token=_TOKEN, user_id=_USER_ID, role="student")
        dao.add_session(session)
        # update_session takes only auth_token after step 3 (user_id param removed)
        dao.update_session(_TOKEN, {"role": "teacher"})
        results = dao.get_sessions_by_auth_token(_TOKEN)
        assert results[0]["role"] == "teacher"
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_delete_session(supabase_required):
    dao = SessionDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        session = Session(auth_token=_TOKEN, user_id=_USER_ID, role="student")
        dao.add_session(session)
        # delete_session takes only auth_token after step 3 (user_id param removed)
        dao.delete_session(_TOKEN)
        results = dao.get_sessions_by_auth_token(_TOKEN)
        assert results == []
    finally:
        _teardown(dao, user_dao)
