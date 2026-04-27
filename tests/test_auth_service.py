"""Unit tests for auth service: hashing, password policy, JWT, and PasswordResetService.

Note: passlib 1.7.4 + bcrypt >=4.x have an incompatibility in detect_wrap_bug, so
_pwd_context is mocked in the hashing tests to avoid that backend-init failure.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest

from services.auth.auth_service import check_password_hash, generate_password_hash
from services.auth.password_policy import validate_password


# ---------------------------------------------------------------------------
# Password hashing (mocked: tests the thin wrapper, not bcrypt internals)
# ---------------------------------------------------------------------------

class TestPasswordHashing:

    @pytest.mark.unit
    @patch("services.auth.auth_service._pwd_context")
    def test_hash_delegates_to_context(self, mock_ctx):
        mock_ctx.hash.return_value = "$2b$fake_hash"
        result = generate_password_hash("MySecret123")
        assert result == "$2b$fake_hash"
        mock_ctx.hash.assert_called_once_with("MySecret123")

    @pytest.mark.unit
    @patch("services.auth.auth_service._pwd_context")
    def test_verify_correct_password(self, mock_ctx):
        mock_ctx.verify.return_value = True
        assert check_password_hash("$2b$fake_hash", "RightPass1") is True
        mock_ctx.verify.assert_called_once_with("RightPass1", "$2b$fake_hash")

    @pytest.mark.unit
    @patch("services.auth.auth_service._pwd_context")
    def test_verify_wrong_password(self, mock_ctx):
        mock_ctx.verify.return_value = False
        assert check_password_hash("$2b$fake_hash", "WrongPass1") is False


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------

class TestPasswordPolicy:

    @pytest.mark.unit
    def test_valid_password(self):
        ok, msg = validate_password("ValidPass99")
        assert ok is True
        assert msg == ""

    @pytest.mark.unit
    def test_too_short(self):
        ok, msg = validate_password("Short1")
        assert ok is False
        assert "10" in msg

    @pytest.mark.unit
    def test_no_digit(self):
        ok, msg = validate_password("OnlyLetters")
        assert ok is False

    @pytest.mark.unit
    def test_no_letter(self):
        ok, msg = validate_password("12345678901")
        assert ok is False

    @pytest.mark.unit
    def test_common_password_rejected(self):
        ok, msg = validate_password("password123")
        assert ok is False

    @pytest.mark.unit
    def test_empty_password(self):
        ok, msg = validate_password("")
        assert ok is False


# ---------------------------------------------------------------------------
# JWT encode / decode
# ---------------------------------------------------------------------------

class TestJWT:

    _SECRET = "test-secret-key"
    _ALGORITHM = "HS256"

    def _mint(self, sub: str, role: str, exp_hours: float = 1.0) -> str:
        payload = {
            "sub": sub,
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=exp_hours),
        }
        return jwt.encode(payload, self._SECRET, algorithm=self._ALGORITHM)

    @pytest.mark.unit
    def test_valid_token_decodes_correctly(self):
        token = self._mint("user-123", "student")
        decoded = jwt.decode(token, self._SECRET, algorithms=[self._ALGORITHM])
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "student"

    @pytest.mark.unit
    def test_expired_token_raises(self):
        token = self._mint("user-123", "student", exp_hours=-1)
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, self._SECRET, algorithms=[self._ALGORITHM])

    @pytest.mark.unit
    def test_wrong_secret_raises(self):
        token = self._mint("user-123", "student")
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "wrong-secret", algorithms=[self._ALGORITHM])


# ---------------------------------------------------------------------------
# PasswordResetService
# ---------------------------------------------------------------------------

def _make_reset_service():
    from services.auth.password_reset_service import PasswordResetService

    svc = PasswordResetService.__new__(PasswordResetService)
    svc.user_dao = MagicMock()
    svc.token_dao = MagicMock()
    svc.rate_limit_dao = MagicMock()
    svc.email_service = MagicMock()
    return svc


class TestPasswordResetService:

    @pytest.mark.unit
    def test_request_always_returns_neutral_message_for_unknown_email(self):
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = None

        result = svc.request_password_reset("nobody@example.com", "127.0.0.1")
        assert result["success"] is True
        assert "reset" in result["message"].lower() or "email" in result["message"].lower()

    @pytest.mark.unit
    def test_request_always_returns_neutral_message_for_known_email(self):
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = {
            "user_id": "u1", "first_name": "Alice", "role": "student"
        }
        svc.token_dao.add_token.return_value = None
        svc.email_service.send_password_reset_email.return_value = {
            "success": True, "message_id": "msg-1"
        }
        svc.rate_limit_dao.set_cooldown.return_value = None

        result = svc.request_password_reset("alice@example.com", "127.0.0.1")
        assert result["success"] is True

    @pytest.mark.unit
    def test_request_rate_limited_still_returns_neutral(self):
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (False, "rate_limited")

        result = svc.request_password_reset("any@example.com", "1.2.3.4")
        assert result["success"] is True

    @pytest.mark.unit
    def test_confirm_invalid_token_returns_failure(self):
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        svc.token_dao.is_token_valid.return_value = (False, None, "not_found")

        ok, msg = svc.confirm_password_reset("badtoken", "ValidPass99", "127.0.0.1")
        assert ok is False

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.generate_password_hash", return_value="$2b$hashed")
    def test_confirm_valid_token_updates_password(self, mock_hash):
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        token_data = {"user_id": "u1", "email": "u@example.com"}
        svc.token_dao.is_token_valid.return_value = (True, token_data, None)
        svc.token_dao.consume_token.return_value = (True, token_data, None)
        svc.user_dao.update.return_value = None

        ok, msg = svc.confirm_password_reset("validtoken", "ValidPass99", "127.0.0.1")
        assert ok is True
        svc.user_dao.update.assert_called_once()

    @pytest.mark.unit
    def test_raw_tokens_are_unique(self):
        tokens = {secrets.token_urlsafe(48) for _ in range(20)}
        assert len(tokens) == 20

    @pytest.mark.unit
    def test_token_hash_is_deterministic(self):
        raw = "somerawtoken"
        h1 = hashlib.sha256(raw.encode()).hexdigest()
        h2 = hashlib.sha256(raw.encode()).hexdigest()
        assert h1 == h2
