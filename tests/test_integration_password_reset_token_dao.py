"""
Integration tests for PasswordResetTokenDAO.
Requires a user FK row.
"""
import pytest
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from data_access.password_reset_token_dao import PasswordResetTokenDAO
from data_access.user_dao import UserDAO
from models.password_reset_token import PasswordResetToken

_USER_ID = "test-integration-prt-user"
_EMAIL = "test-integration-prt@example.com"
_TOKEN_HASH = "test-integration-prt-token-hash"


def _make_token(expires_offset_minutes=45):
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=expires_offset_minutes)).isoformat()
    return PasswordResetToken(
        token_hash=_TOKEN_HASH,
        user_id=_USER_ID,
        email=_EMAIL,
        expires_at=expires_at,
    )


def _setup(user_dao):
    user_dao._insert({
        "user_id": _USER_ID, "first_name": "P", "last_name": "User",
        "email": _EMAIL, "password": "pw", "role": "student",
    })


def _teardown(dao, user_dao):
    try:
        dao.delete_token(_TOKEN_HASH)
    except Exception:
        pass
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_add_and_get_token(supabase_required):
    dao = PasswordResetTokenDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        dao.add_token(_make_token())
        result = dao.get_token(_TOKEN_HASH)
        assert result is not None
        assert result["token_hash"] == _TOKEN_HASH
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_is_token_valid_fresh(supabase_required):
    dao = PasswordResetTokenDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        dao.add_token(_make_token(expires_offset_minutes=45))
        valid, token_data, reason = dao.is_token_valid(_TOKEN_HASH)
        assert valid is True
        assert reason is None
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_is_token_valid_expired(supabase_required):
    dao = PasswordResetTokenDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        expired_token = _make_token(expires_offset_minutes=-10)
        dao.add_token(expired_token)
        valid, token_data, reason = dao.is_token_valid(_TOKEN_HASH)
        assert valid is False
        assert reason == "expired"
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_burn_token(supabase_required):
    dao = PasswordResetTokenDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        dao.add_token(_make_token())
        dao.burn_token(_TOKEN_HASH)
        valid, _, reason = dao.is_token_valid(_TOKEN_HASH)
        assert valid is False
        assert reason == "burned"
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_delete_token(supabase_required):
    dao = PasswordResetTokenDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        dao.add_token(_make_token())
        dao.delete_token(_TOKEN_HASH)
        assert dao.get_token(_TOKEN_HASH) is None
    finally:
        _teardown(dao, user_dao)
