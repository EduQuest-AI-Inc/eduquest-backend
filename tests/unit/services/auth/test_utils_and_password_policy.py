import pytest
from unittest.mock import MagicMock, patch

from utils.token_utils import extract_auth_token, get_user_id_from_token, set_auth_cookie
from utils.validation_utils import validate_required_fields, normalize_email, get_client_ip
from services.auth.password_policy import validate_password, get_password_requirements
from exceptions.auth_error import AuthError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _req(auth_header=None, cookie_header=None, forwarded_for=None, client_host=None):
    req = MagicMock()
    headers = {}
    if auth_header:
        headers['Authorization'] = auth_header
    if cookie_header:
        headers['Cookie'] = cookie_header
    if forwarded_for:
        headers['X-Forwarded-For'] = forwarded_for
    req.headers.get = lambda k, default='': headers.get(k, default)
    if client_host:
        req.client = MagicMock()
        req.client.host = client_host
    else:
        req.client = None
    return req


def _resp():
    r = MagicMock()
    r.set_cookie = MagicMock()
    return r


# ── extract_auth_token ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_extract_token_from_bearer_header():
    req = _req(auth_header="Bearer my-jwt-token")
    assert extract_auth_token(req) == "my-jwt-token"


@pytest.mark.unit
def test_extract_token_bearer_case_insensitive():
    req = _req(auth_header="BEARER my-jwt-token")
    assert extract_auth_token(req) == "my-jwt-token"


@pytest.mark.unit
def test_extract_token_from_cookie_fallback():
    req = _req(cookie_header="auth_token=cookie-token; other=val")
    assert extract_auth_token(req) == "cookie-token"


@pytest.mark.unit
def test_extract_token_cookie_multiple_tokens_returns_last():
    req = _req(cookie_header="auth_token=first; auth_token=second")
    assert extract_auth_token(req) == "second"


@pytest.mark.unit
def test_extract_token_returns_none_if_no_header_no_cookie():
    req = _req()
    assert extract_auth_token(req) is None


@pytest.mark.unit
def test_extract_token_bearer_header_takes_priority_over_cookie():
    req = _req(auth_header="Bearer hdr-token", cookie_header="auth_token=ck-token")
    assert extract_auth_token(req) == "hdr-token"


@pytest.mark.unit
def test_extract_token_non_bearer_authorization_header_ignored():
    req = _req(auth_header="Basic abc123", cookie_header="auth_token=fallback")
    assert extract_auth_token(req) == "fallback"


# ── get_user_id_from_token ────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_user_id_success():
    session_dao = MagicMock()
    session_dao.get_sessions_by_auth_token.return_value = [{"user_id": "u42"}]
    assert get_user_id_from_token("valid-token", session_dao) == "u42"


@pytest.mark.unit
def test_get_user_id_raises_on_none_token():
    session_dao = MagicMock()
    with pytest.raises(AuthError, match="Missing auth token"):
        get_user_id_from_token(None, session_dao)


@pytest.mark.unit
def test_get_user_id_raises_on_empty_string_token():
    session_dao = MagicMock()
    with pytest.raises(AuthError, match="Missing auth token"):
        get_user_id_from_token("", session_dao)


@pytest.mark.unit
def test_get_user_id_raises_on_no_sessions():
    session_dao = MagicMock()
    session_dao.get_sessions_by_auth_token.return_value = []
    with pytest.raises(AuthError, match="Invalid auth token"):
        get_user_id_from_token("bad-tok", session_dao)


@pytest.mark.unit
def test_get_user_id_dao_not_called_on_empty_token():
    session_dao = MagicMock()
    try:
        get_user_id_from_token(None, session_dao)
    except AuthError:
        pass
    session_dao.get_sessions_by_auth_token.assert_not_called()


# ── set_auth_cookie ───────────────────────────────────────────────────────────

@pytest.mark.unit
@patch("utils.token_utils._IS_DEVELOPMENT", False)
def test_set_auth_cookie_production_mode():
    resp = _resp()
    set_auth_cookie(resp, "my-token")
    resp.set_cookie.assert_called_once_with(
        'auth_token', 'my-token',
        httponly=True, secure=True,
        samesite='none', domain='eduquestai.org',
    )


@pytest.mark.unit
@patch("utils.token_utils._IS_DEVELOPMENT", True)
def test_set_auth_cookie_development_mode():
    resp = _resp()
    set_auth_cookie(resp, "dev-token")
    resp.set_cookie.assert_called_once_with('auth_token', 'dev-token', httponly=True, samesite='lax')
    call_kwargs = resp.set_cookie.call_args[1]
    assert "secure" not in call_kwargs
    assert "domain" not in call_kwargs


# ── validate_required_fields ──────────────────────────────────────────────────

@pytest.mark.unit
def test_validate_required_fields_all_present():
    validate_required_fields({"a": "x", "b": "y"}, ["a", "b"])


@pytest.mark.unit
def test_validate_required_fields_one_missing():
    with pytest.raises(ValueError, match="b"):
        validate_required_fields({"a": "x"}, ["a", "b"])


@pytest.mark.unit
def test_validate_required_fields_empty_string_is_missing():
    with pytest.raises(ValueError):
        validate_required_fields({"a": ""}, ["a"])


@pytest.mark.unit
def test_validate_required_fields_none_value_is_missing():
    with pytest.raises(ValueError):
        validate_required_fields({"a": None}, ["a"])


@pytest.mark.unit
def test_validate_required_fields_all_missing_lists_all_in_message():
    with pytest.raises(ValueError) as exc_info:
        validate_required_fields({}, ["x", "y"])
    assert "x" in str(exc_info.value)
    assert "y" in str(exc_info.value)


# ── normalize_email ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Alice@Example.COM  ") == "alice@eduquestai.org"


@pytest.mark.unit
def test_normalize_email_already_normal():
    assert normalize_email("alice@eduquestai.org") == "alice@eduquestai.org"


@pytest.mark.unit
def test_normalize_email_none_returns_empty_string():
    assert normalize_email(None) == ""


@pytest.mark.unit
def test_normalize_email_empty_string_returns_empty_string():
    assert normalize_email("") == ""


# ── get_client_ip ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_client_ip_from_forwarded_header():
    req = _req(forwarded_for="1.2.3.4, 5.6.7.8")
    assert get_client_ip(req) == "1.2.3.4"


@pytest.mark.unit
def test_get_client_ip_single_ip_in_forwarded_header():
    req = _req(forwarded_for="10.0.0.1")
    assert get_client_ip(req) == "10.0.0.1"


@pytest.mark.unit
def test_get_client_ip_fallback_to_request_client():
    req = _req(client_host="9.9.9.9")
    assert get_client_ip(req) == "9.9.9.9"


@pytest.mark.unit
def test_get_client_ip_returns_empty_string_when_no_client():
    req = _req()
    assert get_client_ip(req) == ""


@pytest.mark.unit
def test_get_client_ip_forwarded_header_takes_priority():
    req = _req(forwarded_for="1.1.1.1", client_host="2.2.2.2")
    assert get_client_ip(req) == "1.1.1.1"


# ── validate_password ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_validate_password_empty_string():
    valid, msg = validate_password("")
    assert valid is False
    assert "required" in msg.lower()


@pytest.mark.unit
def test_validate_password_none():
    valid, msg = validate_password(None)
    assert valid is False
    assert "required" in msg.lower()


@pytest.mark.unit
def test_validate_password_too_short():
    valid, msg = validate_password("Abc12345a")  # 9 chars
    assert valid is False
    assert "10" in msg


@pytest.mark.unit
def test_validate_password_exactly_min_length():
    valid, msg = validate_password("Abcde12345")  # 10 chars
    assert valid is True
    assert msg == ""


@pytest.mark.unit
def test_validate_password_common_password_rejected():
    valid, msg = validate_password("password123")
    assert valid is False
    assert "common" in msg.lower()


@pytest.mark.unit
def test_validate_password_common_password_case_insensitive():
    valid, msg = validate_password("PASSWORD123")
    assert valid is False


@pytest.mark.unit
def test_validate_password_no_letter():
    # "2345678901" is not in COMMON_PASSWORDS; 10 digits, no letters
    valid, msg = validate_password("2345678901")
    assert valid is False
    assert "letter" in msg.lower()


@pytest.mark.unit
def test_validate_password_no_digit():
    valid, msg = validate_password("abcdefghij")  # 10 chars, all letters
    assert valid is False
    assert "number" in msg.lower()


@pytest.mark.unit
def test_validate_password_valid_password():
    valid, msg = validate_password("SecurePass9!")
    assert valid is True
    assert msg == ""


@pytest.mark.unit
def test_validate_password_long_password_valid():
    valid, msg = validate_password("ThisIsAVeryLong1Password")
    assert valid is True
    assert msg == ""


@pytest.mark.unit
def test_validate_password_special_chars_accepted():
    valid, msg = validate_password("P@ssword1!!")
    assert valid is True
    assert msg == ""


# ── get_password_requirements ─────────────────────────────────────────────────

@pytest.mark.unit
def test_get_password_requirements_structure():
    result = get_password_requirements()
    assert result["min_length"] == 10
    assert isinstance(result["requirements"], list)
    assert len(result["requirements"]) == 4
    for r in result["requirements"]:
        assert isinstance(r, str) and r


@pytest.mark.unit
def test_get_password_requirements_mentions_min_length_in_requirements():
    reqs = get_password_requirements()["requirements"]
    assert any("10" in r for r in reqs)
