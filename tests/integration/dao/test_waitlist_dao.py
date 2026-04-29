"""Integration tests for the unified WaitlistDAO."""
import pytest
from data_access.waitlist_dao import WaitlistDAO
from data_access.user_dao import UserDAO

_REFERRER_ID = "test-integration-waitlist-referrer"
_REFERRER_EMAIL = "test-integration-referrer@eduquestai.org"


@pytest.mark.integration
def test_join_waitlist(db_user):
    dao = WaitlistDAO()
    try:
        entry = dao.join_waitlist(db_user.user_id, db_user.email)
        assert entry["user_id"] == db_user.user_id
        assert entry["status"] == "pending"
    finally:
        try:
            dao._delete({"user_id": db_user.user_id})
        except Exception:
            pass


@pytest.mark.integration
def test_get_status(db_user):
    dao = WaitlistDAO()
    dao.join_waitlist(db_user.user_id, db_user.email)
    try:
        status = dao.get_status(db_user.user_id)
        assert status["on_waitlist"] is True
        assert status["approved"] is False
    finally:
        try:
            dao._delete({"user_id": db_user.user_id})
        except Exception:
            pass


@pytest.mark.integration
def test_get_waitlist_count(db_user):
    dao = WaitlistDAO()
    before = dao.get_waitlist_count()
    dao.join_waitlist(db_user.user_id, db_user.email)
    try:
        after = dao.get_waitlist_count()
        assert after >= before + 1
    finally:
        try:
            dao._delete({"user_id": db_user.user_id})
        except Exception:
            pass


@pytest.mark.integration
def test_validate_referral_code_valid(supabase_required):
    dao = WaitlistDAO()
    user_dao = UserDAO()
    user_dao._insert({
        "user_id": _REFERRER_ID, "first_name": "W", "last_name": "User",
        "email": _REFERRER_EMAIL, "password": "pw", "role": "teacher",
    })
    try:
        entry = dao.join_waitlist(_REFERRER_ID, _REFERRER_EMAIL)
        referral_code = entry["referral_code"]
        result = dao.validate_referral_code(referral_code)
        assert result["valid"] is True
        assert result["referrer_id"] == _REFERRER_ID
    finally:
        try:
            dao._delete({"user_id": _REFERRER_ID})
        except Exception:
            pass
        user_dao.delete(_REFERRER_ID)


@pytest.mark.integration
def test_validate_referral_code_invalid(supabase_required):
    dao = WaitlistDAO()
    result = dao.validate_referral_code("NOTACODE")
    assert result["valid"] is False


@pytest.mark.integration
def test_approve_user(db_user):
    dao = WaitlistDAO()
    dao.join_waitlist(db_user.user_id, db_user.email)
    try:
        success = dao.approve_user(db_user.user_id)
        assert success is True
        status = dao.get_status(db_user.user_id)
        assert status["approved"] is True
        assert status["status"] == "approved"
    finally:
        try:
            dao._delete({"user_id": db_user.user_id})
        except Exception:
            pass
