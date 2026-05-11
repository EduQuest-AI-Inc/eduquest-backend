"""Unit tests for auth service: hashing, password policy, JWT, and PasswordResetService."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest

from services.auth.auth_service import check_password_hash, generate_password_hash
from services.auth.password_policy import validate_password


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:

    @pytest.mark.unit
    def test_hash_produces_bcrypt_hash(self):
        result = generate_password_hash("MySecret123")
        assert result.startswith("$2b$")

    @pytest.mark.unit
    def test_verify_correct_password(self):
        hashed = generate_password_hash("RightPass1")
        assert check_password_hash(hashed, "RightPass1") is True

    @pytest.mark.unit
    def test_verify_wrong_password(self):
        hashed = generate_password_hash("RightPass1")
        assert check_password_hash(hashed, "WrongPass1") is False


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

    _SECRET = "test-secret-key-that-is-long-enough-for-hs256"
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
            jwt.decode(token, "wrong-secret-key-that-is-long-enough-for-hs256", algorithms=[self._ALGORITHM])


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

        result = svc.request_password_reset("nobody@eduquestai.org", "127.0.0.1")
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

        result = svc.request_password_reset("alice@eduquestai.org", "127.0.0.1")
        assert result["success"] is True

    @pytest.mark.unit
    def test_request_rate_limited_still_returns_neutral(self):
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (False, "rate_limited")

        result = svc.request_password_reset("any@eduquestai.org", "1.2.3.4")
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
        token_data = {"user_id": "u1", "email": "u@eduquestai.org"}
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


# ---------------------------------------------------------------------------
# PasswordResetService — rate-limit enforcement
# ---------------------------------------------------------------------------

class TestPasswordResetRateLimit:

    @pytest.mark.unit
    def test_confirm_rate_limited_returns_failure(self):
        """confirm_password_reset must return False when the IP is rate-limited."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (False, "too_many_attempts")

        ok, msg = svc.confirm_password_reset("anytoken", "ValidPass99", "1.2.3.4")

        assert ok is False
        assert msg  # some non-empty error message

    @pytest.mark.unit
    def test_confirm_rate_limited_does_not_query_token_dao(self):
        """When the confirm endpoint is rate-limited the token DAO must never be queried."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (False, "too_many_attempts")

        svc.confirm_password_reset("anytoken", "ValidPass99", "1.2.3.4")

        svc.token_dao.is_token_valid.assert_not_called()

    @pytest.mark.unit
    def test_request_rate_limited_does_not_call_record_request(self):
        """When the request endpoint is rate-limited, record_request must NOT be called."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (False, "rate_limited")

        svc.request_password_reset("any@eduquestai.org", "1.2.3.4")

        svc.rate_limit_dao.record_request.assert_not_called()

    @pytest.mark.unit
    def test_request_not_rate_limited_calls_record_request(self):
        """When the request endpoint is not rate-limited, record_request must be called."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = None  # unknown email path

        svc.request_password_reset("nobody@eduquestai.org", "1.2.3.4")

        svc.rate_limit_dao.record_request.assert_called_once()


# ---------------------------------------------------------------------------
# PasswordResetService — token expiry paths
# ---------------------------------------------------------------------------

class TestPasswordResetTokenExpiry:

    @pytest.mark.unit
    def test_confirm_expired_token_returns_failure(self):
        """An expired token must cause confirm_password_reset to return False."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        # Simulate the DAO marking the token as expired but present
        token_data = {"user_id": "u1", "email": "u@eduquestai.org"}
        svc.token_dao.is_token_valid.return_value = (False, token_data, "expired")

        ok, msg = svc.confirm_password_reset("expiredtoken", "ValidPass99", "127.0.0.1")

        assert ok is False
        assert msg  # neutral/error message must be non-empty

    @pytest.mark.unit
    def test_confirm_expired_token_does_not_consume(self):
        """An expired token must not be consumed (consume_token must not be called)."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        token_data = {"user_id": "u1", "email": "u@eduquestai.org"}
        svc.token_dao.is_token_valid.return_value = (False, token_data, "expired")

        svc.confirm_password_reset("expiredtoken", "ValidPass99", "127.0.0.1")

        svc.token_dao.consume_token.assert_not_called()

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.generate_password_hash", return_value="$2b$hashed")
    def test_confirm_valid_token_returns_success(self, mock_hash):
        """A fresh, valid token must allow confirm_password_reset to succeed."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        token_data = {"user_id": "u1", "email": "u@eduquestai.org"}
        svc.token_dao.is_token_valid.return_value = (True, token_data, None)
        svc.token_dao.consume_token.return_value = (True, token_data, None)
        svc.user_dao.update.return_value = None

        ok, msg = svc.confirm_password_reset("freshtoken", "ValidPass99", "127.0.0.1")

        assert ok is True
        assert msg  # success message must be non-empty

    @pytest.mark.unit
    def test_confirm_already_used_token_returns_failure(self):
        """A token that was already consumed must not allow a second reset."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        svc.token_dao.is_token_valid.return_value = (False, None, "already_used")

        ok, msg = svc.confirm_password_reset("usedtoken", "ValidPass99", "127.0.0.1")

        assert ok is False


# ---------------------------------------------------------------------------
# PasswordResetService — email-not-found path
# ---------------------------------------------------------------------------

class TestPasswordResetEmailNotFound:

    @pytest.mark.unit
    def test_unknown_email_returns_neutral_message(self):
        """Unknown email must return success=True with a neutral message (no enumeration)."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = None

        result = svc.request_password_reset("ghost@eduquestai.org", "10.0.0.1")

        assert result["success"] is True
        assert result.get("message")

    @pytest.mark.unit
    def test_unknown_email_does_not_send_email(self):
        """No email must be dispatched when the address is not registered."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = None

        svc.request_password_reset("ghost@eduquestai.org", "10.0.0.1")

        svc.email_service.send_password_reset_email.assert_not_called()

    @pytest.mark.unit
    def test_unknown_email_does_not_create_token(self):
        """No reset token must be persisted when the address is not registered."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = None

        svc.request_password_reset("ghost@eduquestai.org", "10.0.0.1")

        svc.token_dao.add_token.assert_not_called()

    @pytest.mark.unit
    def test_unknown_email_message_matches_known_email_message(self):
        """The response message for an unknown email must equal the message for a known email
        so that callers cannot enumerate registered addresses by comparing responses."""
        svc_unknown = _make_reset_service()
        svc_unknown.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc_unknown.user_dao.get_by_email.return_value = None
        result_unknown = svc_unknown.request_password_reset("ghost@eduquestai.org", "10.0.0.1")

        svc_known = _make_reset_service()
        svc_known.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc_known.user_dao.get_by_email.return_value = {
            "user_id": "u2", "first_name": "Bob", "role": "student"
        }
        svc_known.token_dao.add_token.return_value = None
        svc_known.email_service.send_password_reset_email.return_value = {
            "success": True, "message_id": "msg-2"
        }
        svc_known.rate_limit_dao.set_cooldown.return_value = None
        result_known = svc_known.request_password_reset("bob@eduquestai.org", "10.0.0.1")

        assert result_unknown["message"] == result_known["message"]


# ---------------------------------------------------------------------------
# PasswordResetService — security-event logging
# ---------------------------------------------------------------------------

class TestPasswordResetSecurityEventLogging:

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.logger")
    def test_rate_limited_request_logs_security_event(self, mock_logger):
        """A rate-limited request must emit a security-relevant log entry."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (False, "rate_limited")

        svc.request_password_reset("any@eduquestai.org", "1.2.3.4")

        assert mock_logger.info.called
        log_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "RATE_LIMITED" in log_messages

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.logger")
    def test_user_not_found_logs_security_event(self, mock_logger):
        """A request for an unknown email must emit a security-relevant log entry."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_rate_limit.return_value = (True, None)
        svc.user_dao.get_by_email.return_value = None

        svc.request_password_reset("ghost@eduquestai.org", "1.2.3.4")

        assert mock_logger.info.called
        log_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "NOT_FOUND" in log_messages

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.logger")
    def test_confirm_rate_limited_logs_security_event(self, mock_logger):
        """A rate-limited confirm attempt must emit a security-relevant log entry."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (False, "too_many_attempts")

        svc.confirm_password_reset("anytoken", "ValidPass99", "5.6.7.8")

        assert mock_logger.info.called
        log_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "RATE_LIMITED" in log_messages

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.logger")
    def test_invalid_token_confirm_logs_security_event(self, mock_logger):
        """An invalid-token confirm attempt must emit a security-relevant log entry."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        svc.token_dao.is_token_valid.return_value = (False, None, "not_found")

        svc.confirm_password_reset("badtoken", "ValidPass99", "5.6.7.8")

        assert mock_logger.info.called
        log_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "INVALID" in log_messages or "NOT_FOUND" in log_messages

    @pytest.mark.unit
    @patch("services.auth.password_reset_service.generate_password_hash", return_value="$2b$hashed")
    @patch("services.auth.password_reset_service.logger")
    def test_successful_reset_logs_success_event(self, mock_logger, mock_hash):
        """A successful password reset must emit a SUCCESS log entry."""
        svc = _make_reset_service()
        svc.rate_limit_dao.check_confirm_rate_limit.return_value = (True, None)
        svc.rate_limit_dao.record_confirm_attempt.return_value = None
        token_data = {"user_id": "u1", "email": "u@eduquestai.org"}
        svc.token_dao.is_token_valid.return_value = (True, token_data, None)
        svc.token_dao.consume_token.return_value = (True, token_data, None)
        svc.user_dao.update.return_value = None

        svc.confirm_password_reset("goodtoken", "ValidPass99", "127.0.0.1")

        assert mock_logger.info.called
        log_messages = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "SUCCESS" in log_messages
