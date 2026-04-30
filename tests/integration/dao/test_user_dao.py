import pytest
from data_access.user_dao import UserDAO

_ID = "test-integration-user-dao"
_EMAIL = "test-integration-user@eduquestai.org"


def _insert(dao):
    dao._insert({
        "user_id": _ID,
        "first_name": "Test",
        "last_name": "User",
        "email": _EMAIL,
        "password": "hashed",
        "role": "student",
    })


@pytest.mark.integration
def test_get_by_id(supabase_required):
    dao = UserDAO()
    try:
        _insert(dao)
        result = dao.get_by_id(_ID)
        assert result is not None
        assert result["user_id"] == _ID
    finally:
        dao.delete(_ID)


@pytest.mark.integration
def test_get_by_email(supabase_required):
    dao = UserDAO()
    try:
        _insert(dao)
        result = dao.get_by_email(_EMAIL)
        assert result is not None
        assert result["email"] == _EMAIL
    finally:
        dao.delete(_ID)


@pytest.mark.integration
def test_update(supabase_required):
    dao = UserDAO()
    try:
        _insert(dao)
        dao.update(_ID, {"first_name": "Updated"})
        result = dao.get_by_id(_ID)
        assert result["first_name"] == "Updated"
    finally:
        dao.delete(_ID)


@pytest.mark.integration
def test_delete(supabase_required):
    dao = UserDAO()
    _insert(dao)
    dao.delete(_ID)
    assert dao.get_by_id(_ID) is None
