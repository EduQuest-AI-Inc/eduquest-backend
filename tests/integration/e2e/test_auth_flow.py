# tests/test_integration_auth.py
"""
Integration tests for the end-to-end auth flow.

Requires:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, JWT_SECRET_KEY in .env
  TEST_USERNAME, TEST_PASSWORD, TEST_ROLE in .env pointing to a pre-existing Supabase user

Run:
  cd eduquest-backend
  source venv/bin/activate
  pytest tests/test_integration_auth.py -v
"""
import os
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from main import app

TEST_USERNAME = os.environ.get("TEST_USERNAME", "")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "")
TEST_ROLE     = os.environ.get("TEST_ROLE", "teacher")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(supabase_required, client):
    """Log in once per module; return the JWT for use in protected-route tests."""
    response = client.post("/auth/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "role": TEST_ROLE,
    })
    assert response.status_code == 200, (
        f"auth_token fixture: login failed {response.status_code}: {response.text}"
    )
    return response.json()["token"]


# ---------------------------------------------------------------------------
# Primary test
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.auth
def test_login_and_access_protected_route(supabase_required, client):
    """Full auth flow: login → receive JWT → access protected route → 200."""

    # Step 1 — Send login request
    login_payload = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "role": TEST_ROLE,
    }
    login_response = client.post("/auth/login", json=login_payload)

    # Step 2 — Assert login response
    assert login_response.status_code == 200, (
        f"Expected 200, got {login_response.status_code}: {login_response.text}"
    )
    body = login_response.json()
    assert "token" in body, f"Response missing 'token' key: {body}"
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 0

    # Step 3 — Extract JWT
    token = body["token"]

    # Step 4 — Call protected route with Bearer token
    profile_response = client.get(
        "/user/profile",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Step 5 — Assert protected route success
    assert profile_response.status_code == 200, (
        f"Expected 200, got {profile_response.status_code}: {profile_response.text}"
    )
    profile = profile_response.json()
    assert "role" in profile, f"Profile response missing 'role': {profile}"
    assert profile["role"] == TEST_ROLE


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.auth
def test_login_invalid_credentials(supabase_required, client):
    """Wrong password must return 401 with 'Invalid credentials'."""
    response = client.post("/auth/login", json={
        "username": TEST_USERNAME,
        "password": "definitely-wrong-password-xyz",
        "role": TEST_ROLE,
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.integration
@pytest.mark.auth
def test_protected_route_rejects_missing_token(supabase_required, client):
    """No token in header or cookie must return 401 with 'Missing auth token'."""
    response = client.get("/user/profile")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing auth token"


@pytest.mark.integration
@pytest.mark.auth
def test_protected_route_rejects_invalid_token(supabase_required, client):
    """A malformed JWT must return 401 with 'Invalid token'."""
    response = client.get(
        "/user/profile",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.integration
@pytest.mark.auth
def test_protected_route_rejects_expired_token(supabase_required, client):
    """A correctly signed but expired JWT must return 401 with 'Token expired'."""
    expired_token = pyjwt.encode(
        {
            "sub": TEST_USERNAME,
            "role": TEST_ROLE,
            "exp": datetime.now(timezone.utc) - timedelta(hours=2),
        },
        os.environ["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    response = client.get(
        "/user/profile",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"
