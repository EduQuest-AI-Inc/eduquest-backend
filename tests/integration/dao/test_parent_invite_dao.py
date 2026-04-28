"""Integration tests for ParentInviteDAO."""
import pytest
from data_access.parent_invite_dao import ParentInviteDAO
from models.parent_invite import ParentInvite

_CODE = "TESTSTP8"


@pytest.mark.integration
def test_create_and_get_invite(db_user):
    dao = ParentInviteDAO()
    invite = ParentInvite(code=_CODE, user_id=db_user.user_id)
    dao.create_invite(invite)
    try:
        result = dao.get_invite_by_code(_CODE)
        assert result is not None
        assert result["code"] == _CODE
        assert result["used"] is False
    finally:
        dao._delete({"code": _CODE})


@pytest.mark.integration
def test_mark_used(db_user):
    dao = ParentInviteDAO()
    invite = ParentInvite(code=_CODE, user_id=db_user.user_id)
    dao.create_invite(invite)
    try:
        dao.mark_used(_CODE)
        result = dao.get_invite_by_code(_CODE)
        assert result["used"] is True
    finally:
        dao._delete({"code": _CODE})
