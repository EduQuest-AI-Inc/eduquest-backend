"""Integration tests for PasswordResetTokenDAO."""
import pytest
from datetime import datetime, timedelta, timezone
from data_access.password_reset_token_dao import PasswordResetTokenDAO
from models.password_reset_token import PasswordResetToken

_TOKEN_HASH = "test-integration-prt-token-hash"


def _make_token(user_id, email, expires_offset_minutes=45):
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=expires_offset_minutes)).isoformat()
    return PasswordResetToken(
        token_hash=_TOKEN_HASH,
        user_id=user_id,
        email=email,
        expires_at=expires_at,
    )


@pytest.mark.integration
def test_add_and_get_token(db_user):
    dao = PasswordResetTokenDAO()
    dao.add_token(_make_token(db_user.user_id, db_user.email))
    try:
        result = dao.get_token(_TOKEN_HASH)
        assert result is not None
        assert result["token_hash"] == _TOKEN_HASH
    finally:
        dao.delete_token(_TOKEN_HASH)


@pytest.mark.integration
def test_is_token_valid_fresh(db_user):
    dao = PasswordResetTokenDAO()
    dao.add_token(_make_token(db_user.user_id, db_user.email, expires_offset_minutes=45))
    try:
        valid, token_data, reason = dao.is_token_valid(_TOKEN_HASH)
        assert valid is True
        assert reason is None
    finally:
        dao.delete_token(_TOKEN_HASH)


@pytest.mark.integration
def test_is_token_valid_expired(db_user):
    dao = PasswordResetTokenDAO()
    dao.add_token(_make_token(db_user.user_id, db_user.email, expires_offset_minutes=-10))
    try:
        valid, token_data, reason = dao.is_token_valid(_TOKEN_HASH)
        assert valid is False
        assert reason == "expired"
    finally:
        dao.delete_token(_TOKEN_HASH)


@pytest.mark.integration
def test_burn_token(db_user):
    dao = PasswordResetTokenDAO()
    dao.add_token(_make_token(db_user.user_id, db_user.email))
    try:
        dao.burn_token(_TOKEN_HASH)
        valid, _, reason = dao.is_token_valid(_TOKEN_HASH)
        assert valid is False
        assert reason == "burned"
    finally:
        dao.delete_token(_TOKEN_HASH)


@pytest.mark.integration
def test_delete_token(db_user):
    dao = PasswordResetTokenDAO()
    dao.add_token(_make_token(db_user.user_id, db_user.email))
    dao.delete_token(_TOKEN_HASH)
    assert dao.get_token(_TOKEN_HASH) is None
