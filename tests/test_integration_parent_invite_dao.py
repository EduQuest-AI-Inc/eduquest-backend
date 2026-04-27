"""
Integration tests for ParentInviteDAO.
Requires a user row for the FK constraint.
"""
import pytest
from data_access.parent_invite_dao import ParentInviteDAO
from data_access.user_dao import UserDAO
from models.user import User
from models.parent_invite import ParentInvite

_CODE = "TESTSTP8"
_USER_ID = "test-step8-invite-user"


def _setup(user_dao):
    user_dao.add_user(User(
        user_id=_USER_ID, first_name="I", last_name="User",
        email="test-step8-invite@example.com", password="pw", role="parent",
    ))


def _teardown(dao, user_dao):
    try:
        dao._delete({"code": _CODE})
    except Exception:
        pass
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_create_and_get_invite(supabase_required):
    dao = ParentInviteDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        invite = ParentInvite(code=_CODE, user_id=_USER_ID)
        dao.create_invite(invite)
        result = dao.get_invite_by_code(_CODE)
        assert result is not None
        assert result["code"] == _CODE
        assert result["used"] is False
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_mark_used(supabase_required):
    dao = ParentInviteDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        invite = ParentInvite(code=_CODE, user_id=_USER_ID)
        dao.create_invite(invite)
        dao.mark_used(_CODE)
        result = dao.get_invite_by_code(_CODE)
        assert result["used"] is True
    finally:
        _teardown(dao, user_dao)
