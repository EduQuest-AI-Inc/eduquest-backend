"""Integration tests for SessionDAO."""
import pytest
from data_access.session_dao import SessionDAO
from models.session import Session

_TOKEN = "test-integration-session-token"


@pytest.mark.integration
def test_add_and_get_session(db_user):
    dao = SessionDAO()
    session = Session(auth_token=_TOKEN, user_id=db_user.user_id, role="student")
    dao.add_session(session)
    try:
        results = dao.get_sessions_by_auth_token(_TOKEN)
        assert len(results) == 1
        assert results[0]["user_id"] == db_user.user_id
    finally:
        dao.delete_session(_TOKEN)


@pytest.mark.integration
def test_update_session(db_user):
    dao = SessionDAO()
    session = Session(auth_token=_TOKEN, user_id=db_user.user_id, role="student")
    dao.add_session(session)
    try:
        dao.update_session(_TOKEN, {"role": "teacher"})
        results = dao.get_sessions_by_auth_token(_TOKEN)
        assert results[0]["role"] == "teacher"
    finally:
        dao.delete_session(_TOKEN)


@pytest.mark.integration
def test_delete_session(db_user):
    dao = SessionDAO()
    session = Session(auth_token=_TOKEN, user_id=db_user.user_id, role="student")
    dao.add_session(session)
    dao.delete_session(_TOKEN)
    results = dao.get_sessions_by_auth_token(_TOKEN)
    assert results == []
