from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest

from exceptions.auth_error import AuthError
from exceptions.validation_error import ValidationError
from services.auth.age_screen_service import AgeScreenService


def _service() -> AgeScreenService:
    return AgeScreenService(session_dao=MagicMock(), rate_limit_dao=MagicMock())


@pytest.mark.unit
def test_compute_age_band_is_conservative_during_birth_month():
    now = datetime.now(timezone.utc)
    previous_month = 12 if now.month == 1 else now.month - 1
    previous_month_year = now.year - 19 if now.month == 1 else now.year - 18
    assert AgeScreenService._compute_age_band(birth_month=now.month, birth_year=now.year - 13) == "under_13"
    assert AgeScreenService._compute_age_band(birth_month=now.month, birth_year=now.year - 18) == "13_to_17"
    assert AgeScreenService._compute_age_band(birth_month=previous_month, birth_year=previous_month_year) == "18_plus"


@pytest.mark.unit
def test_create_stores_only_derived_band_and_token_hash():
    service = _service()
    service.rate_limit_dao.allow.return_value = True
    now = datetime.now(timezone.utc)
    birth_year = now.year - 20

    raw_token, age_band = service.create(birth_month=1, birth_year=birth_year, request_ip="127.0.0.1")

    assert age_band == "18_plus"
    record = service.session_dao.create.call_args.args[0]
    assert record["token_hash"] != raw_token
    assert record["age_band"] == "18_plus"
    assert "birth_month" not in record
    assert "birth_year" not in record


@pytest.mark.unit
def test_create_rejects_rate_limited_request():
    service = _service()
    service.rate_limit_dao.allow.return_value = False

    with pytest.raises(ValidationError, match="Too many"):
        service.create(birth_month=5, birth_year=2008, request_ip="127.0.0.1")


@pytest.mark.unit
def test_consume_rejects_replay_or_expired_token():
    service = _service()
    service.session_dao.consume.return_value = None

    with pytest.raises(AuthError, match="expired or was already used"):
        service.consume("opaque", expected_band="18_plus")


@pytest.mark.unit
def test_consume_rejects_band_mismatch():
    service = _service()
    service.session_dao.consume.return_value = {"age_band": "under_13"}

    with pytest.raises(AuthError, match="does not match"):
        service.consume("opaque", expected_band="18_plus")
