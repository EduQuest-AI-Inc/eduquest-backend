"""
Integration tests for the unified WaitlistDAO.
waitlist.user_id has a FK to user, so we create/delete user rows in setup/teardown.
"""
import pytest
from data_access.waitlist_dao import WaitlistDAO
from data_access.user_dao import UserDAO

_USER_ID = "test-step8-waitlist-user"
_EMAIL = "test-step8-waitlist@example.com"
_REFERRER_ID = "test-step8-waitlist-referrer"
_REFERRER_EMAIL = "test-step8-referrer@example.com"


def _setup_user(user_dao, user_id, email):
    user_dao._insert({
        "user_id": user_id, "first_name": "W", "last_name": "User",
        "email": email, "password": "pw", "role": "teacher",
    })


def _teardown(dao, user_dao):
    try:
        dao._delete({"user_id": _USER_ID})
    except Exception:
        pass
    try:
        dao._delete({"user_id": _REFERRER_ID})
    except Exception:
        pass
    try:
        user_dao.delete(_REFERRER_ID)
    except Exception:
        pass
    try:
        user_dao.delete(_USER_ID)
    except Exception:
        pass


@pytest.mark.integration
def test_join_waitlist(supabase_required):
    dao = WaitlistDAO()
    user_dao = UserDAO()
    _setup_user(user_dao, _USER_ID, _EMAIL)
    try:
        entry = dao.join_waitlist(_USER_ID, _EMAIL)
        assert entry["user_id"] == _USER_ID
        assert entry["status"] == "pending"
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_get_status(supabase_required):
    dao = WaitlistDAO()
    user_dao = UserDAO()
    _setup_user(user_dao, _USER_ID, _EMAIL)
    try:
        dao.join_waitlist(_USER_ID, _EMAIL)
        status = dao.get_status(_USER_ID)
        assert status["on_waitlist"] is True
        assert status["approved"] is False
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_get_waitlist_count(supabase_required):
    dao = WaitlistDAO()
    user_dao = UserDAO()
    _setup_user(user_dao, _USER_ID, _EMAIL)
    try:
        before = dao.get_waitlist_count()
        dao.join_waitlist(_USER_ID, _EMAIL)
        after = dao.get_waitlist_count()
        assert after >= before + 1
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_validate_referral_code_valid(supabase_required):
    dao = WaitlistDAO()
    user_dao = UserDAO()
    _setup_user(user_dao, _REFERRER_ID, _REFERRER_EMAIL)
    try:
        entry = dao.join_waitlist(_REFERRER_ID, _REFERRER_EMAIL)
        referral_code = entry["referral_code"]
        result = dao.validate_referral_code(referral_code)
        assert result["valid"] is True
        assert result["referrer_id"] == _REFERRER_ID
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_validate_referral_code_invalid(supabase_required):
    dao = WaitlistDAO()
    result = dao.validate_referral_code("NOTACODE")
    assert result["valid"] is False


@pytest.mark.integration
def test_approve_user(supabase_required):
    dao = WaitlistDAO()
    user_dao = UserDAO()
    _setup_user(user_dao, _USER_ID, _EMAIL)
    try:
        dao.join_waitlist(_USER_ID, _EMAIL)
        success = dao.approve_user(_USER_ID)
        assert success is True
        status = dao.get_status(_USER_ID)
        assert status["approved"] is True
        assert status["status"] == "approved"
    finally:
        _teardown(dao, user_dao)
