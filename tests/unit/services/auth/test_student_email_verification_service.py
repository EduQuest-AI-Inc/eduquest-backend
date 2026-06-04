from unittest.mock import MagicMock

import pytest

from exceptions.auth_error import AuthError
from exceptions.validation_error import ValidationError
from services.auth.student_email_verification_service import StudentEmailVerificationService


def _service() -> StudentEmailVerificationService:
    return StudentEmailVerificationService(
        verification_dao=MagicMock(),
        age_screen_dao=MagicMock(),
        rate_limit_dao=MagicMock(),
        email_service=MagicMock(),
        secret="test-secret",
    )


@pytest.mark.unit
def test_request_code_stores_only_hashed_email_and_code():
    service = _service()
    service.age_screen_dao.get_valid.return_value = {"age_band": "18_plus"}
    service.rate_limit_dao.allow.return_value = True
    service.email_service.send_student_email_verification_code.return_value = {"success": True}

    service.request_code(email=" Adult@Example.com ", age_screen_token="opaque", request_ip="127.0.0.1")

    record = service.verification_dao.create.call_args.args[0]
    assert record["email_hmac"] != "adult@example.com"
    assert "email" not in record
    assert "code" not in record
    service.email_service.send_student_email_verification_code.assert_called_once()


@pytest.mark.unit
def test_request_code_requires_adult_age_screen():
    service = _service()
    service.age_screen_dao.get_valid.return_value = {"age_band": "under_13"}

    with pytest.raises(AuthError, match="only after an adult age screen"):
        service.request_code(email="adult@example.com", age_screen_token="opaque", request_ip="127.0.0.1")


@pytest.mark.unit
def test_request_code_enforces_rate_limit():
    service = _service()
    service.age_screen_dao.get_valid.return_value = {"age_band": "18_plus"}
    service.rate_limit_dao.allow.return_value = False

    with pytest.raises(ValidationError, match="Too many"):
        service.request_code(email="adult@example.com", age_screen_token="opaque", request_ip="127.0.0.1")


@pytest.mark.unit
def test_confirm_code_returns_opaque_cookie_token():
    service = _service()
    service.rate_limit_dao.allow.return_value = True
    service.verification_dao.confirm.return_value = {"verified_at": "now"}

    token = service.confirm_code(email="adult@example.com", code="123456", request_ip="127.0.0.1")

    assert token
    kwargs = service.verification_dao.confirm.call_args.kwargs
    assert kwargs["verified_token_hash"] != token
    assert kwargs["code_hash"] != "123456"


@pytest.mark.unit
def test_consume_rejects_replayed_or_expired_token():
    service = _service()
    service.verification_dao.consume.return_value = None

    with pytest.raises(AuthError, match="expired or was already used"):
        service.consume(email="adult@example.com", raw_token="opaque")
