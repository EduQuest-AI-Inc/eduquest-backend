"""
Unit tests for PasswordResetRateLimitDAO.
This DAO stores state in Supabase but these tests verify the pure-Python
rate-limit logic by mocking the internal _get_count, _increment_counter, and
_is_on_cooldown helpers so no DB connection is needed.
"""
import pytest
from unittest.mock import MagicMock
from data_access.password_reset_rate_limit_dao import PasswordResetRateLimitDAO


def _dao():
    dao = PasswordResetRateLimitDAO.__new__(PasswordResetRateLimitDAO)
    dao.table_name = 'password_reset_rate_limit'
    dao.client = MagicMock()
    dao.MAX_REQUESTS_PER_IP_EMAIL = 5
    dao.MAX_REQUESTS_PER_IP = 20
    dao.WINDOW_SIZE_SECONDS = 900
    dao.COOLDOWN_SECONDS = 300
    return dao


@pytest.mark.unit
def test_check_rate_limit_allows_first_request():
    dao = _dao()
    dao._is_on_cooldown = MagicMock(return_value=False)
    dao._get_count = MagicMock(return_value=0)

    allowed, msg = dao.check_rate_limit("1.2.3.4", "user@example.com")

    assert allowed is True
    assert msg == ""


@pytest.mark.unit
def test_check_rate_limit_blocks_after_ip_email_limit():
    dao = _dao()
    dao._is_on_cooldown = MagicMock(return_value=False)
    # ip_email count is at limit; ip count is under
    dao._get_count = MagicMock(side_effect=[5, 0])

    allowed, reason = dao.check_rate_limit("1.2.3.4", "user@example.com")

    assert allowed is False
    assert reason == "ip_email_limit"


@pytest.mark.unit
def test_set_cooldown_then_blocked():
    dao = _dao()
    dao._is_on_cooldown = MagicMock(return_value=True)
    dao._get_count = MagicMock(return_value=0)

    allowed, reason = dao.check_rate_limit("1.2.3.4", "user@example.com")

    assert allowed is False
    assert reason == "cooldown"


@pytest.mark.unit
def test_check_confirm_rate_limit_allows():
    dao = _dao()
    dao._get_count = MagicMock(return_value=0)
    # patch _get_window_start so key generation works
    dao._get_window_start = MagicMock(return_value=1000000)

    allowed, msg = dao.check_confirm_rate_limit("1.2.3.4")

    assert allowed is True
    assert msg == ""


@pytest.mark.unit
def test_check_confirm_rate_limit_blocks_after_limit():
    dao = _dao()
    dao._get_window_start = MagicMock(return_value=1000000)
    dao._get_count = MagicMock(return_value=20)

    allowed, reason = dao.check_confirm_rate_limit("1.2.3.4")

    assert allowed is False
    assert reason == "ip_limit"
