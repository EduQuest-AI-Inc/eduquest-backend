"""
Unit tests for routers/deps.py — get_auth and require_student_viewer dependencies.

A fresh minimal FastAPI app is built per test so that the ParentService /
EnrollmentService instances captured inside the closure can be swapped out
via patch before require_student_viewer() is called.
"""
import time
import pytest
import jwt as pyjwt
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from routers.deps import require_student_viewer, get_auth, AuthPayload, Role

TEST_SECRET = "test-supabase-jwt-secret-key-32b!"


def _make_token(app_metadata: dict, expired: bool = False) -> str:
    """Build a minimal Supabase-shaped JWT signed with TEST_SECRET."""
    now = int(time.time())
    payload = {
        "sub": "some-uuid",
        "aud": "authenticated",
        "iat": now,
        "exp": now - 10 if expired else now + 3600,
        "app_metadata": app_metadata,
    }
    return pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_app(mock_parent_svc: MagicMock, mock_enrollment_svc: MagicMock) -> FastAPI:
    """
    Build a minimal FastAPI app whose single route uses require_student_viewer.
    The service instances captured inside the closure are controlled via patch.
    """
    with patch(
        "services.parent.parent_service.ParentService",
        return_value=mock_parent_svc,
    ), patch(
        "services.enrollment.enrollment_service.EnrollmentService",
        return_value=mock_enrollment_svc,
    ):
        dep = require_student_viewer("user_id")

    mini_app = FastAPI()

    @mini_app.get("/probe")
    def probe(auth: AuthPayload = Depends(dep)):
        return {"sub": auth.sub, "role": auth.role}

    return mini_app


def _client(mini_app: FastAPI, role: Role, sub: str = "caller-1") -> TestClient:
    mini_app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub=sub, role=role, token="test-token"
    )
    return TestClient(mini_app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_no_student_id_passes_through_as_own_data():
    mini_app = _build_app(MagicMock(), MagicMock())
    with _client(mini_app, Role.STUDENT) as client:
        resp = client.get("/probe")
    assert resp.status_code == 200


@pytest.mark.unit
def test_parent_linked_student_allowed():
    parent_svc = MagicMock()
    parent_svc.get_linked_student_ids.return_value = ["student-1", "student-2"]
    mini_app = _build_app(parent_svc, MagicMock())
    with _client(mini_app, Role.PARENT) as client:
        resp = client.get("/probe?user_id=student-1")
    assert resp.status_code == 200


@pytest.mark.unit
def test_parent_unlinked_student_returns_403():
    parent_svc = MagicMock()
    parent_svc.get_linked_student_ids.return_value = ["other-student"]
    mini_app = _build_app(parent_svc, MagicMock())
    with _client(mini_app, Role.PARENT) as client:
        resp = client.get("/probe?user_id=student-1")
    assert resp.status_code == 403


@pytest.mark.unit
def test_teacher_with_access_allowed():
    enrollment_svc = MagicMock()
    enrollment_svc.has_teacher_access_to_student.return_value = True
    mini_app = _build_app(MagicMock(), enrollment_svc)
    with _client(mini_app, Role.TEACHER) as client:
        resp = client.get("/probe?user_id=student-1")
    assert resp.status_code == 200
    enrollment_svc.has_teacher_access_to_student.assert_called_once_with("caller-1", "student-1")


@pytest.mark.unit
def test_teacher_without_access_returns_403():
    enrollment_svc = MagicMock()
    enrollment_svc.has_teacher_access_to_student.return_value = False
    mini_app = _build_app(MagicMock(), enrollment_svc)
    with _client(mini_app, Role.TEACHER) as client:
        resp = client.get("/probe?user_id=student-1")
    assert resp.status_code == 403


@pytest.mark.unit
def test_student_role_with_foreign_user_id_returns_403():
    mini_app = _build_app(MagicMock(), MagicMock())
    with _client(mini_app, Role.STUDENT) as client:
        resp = client.get("/probe?user_id=some-other-student")
    assert resp.status_code == 403


# ── get_auth — Supabase JWT validation ───────────────────────────────────────

def _auth_app() -> FastAPI:
    mini = FastAPI()

    @mini.get("/me")
    def me(auth: AuthPayload = Depends(get_auth)):
        return {"sub": auth.sub, "role": auth.role.value}

    return mini


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
@patch("routers.deps.StudentDAO")
def test_get_auth_valid_token(mock_student_dao):
    # compliance_status claim in JWT — StudentDAO must NOT be called
    token = _make_token({"username": "testuser", "role": "student", "compliance_status": "active"})
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"sub": "testuser", "role": "student"}
    mock_student_dao.return_value.get_student_by_id.assert_not_called()


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
@patch("routers.deps.StudentDAO")
def test_get_auth_blocks_quarantined_student_token(mock_student_dao):
    # compliance_status claim in JWT — StudentDAO must NOT be called
    token = _make_token({"username": "testuser", "role": "student", "compliance_status": "quarantined_age_review"})
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "STUDENT_COMPLIANCE_REVIEW_REQUIRED"
    mock_student_dao.return_value.get_student_by_id.assert_not_called()


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
@patch("routers.deps.StudentDAO")
def test_enforce_compliance_fallback_to_db(mock_student_dao):
    # No compliance claim in JWT → should fall back to StudentDAO
    mock_student_dao.return_value.get_student_by_id.return_value = {"compliance_status": "active"}
    token = _make_token({"username": "testuser", "role": "student"})
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    mock_student_dao.return_value.get_student_by_id.assert_called_once_with("testuser")


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
@patch("routers.deps.StudentDAO")
def test_enforce_compliance_legacy_review_due_future(mock_student_dao):
    from datetime import datetime, timezone, timedelta
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    token = _make_token({
        "username": "testuser",
        "role": "student",
        "compliance_status": "legacy_review_due",
        "compliance_review_due_at": future,
    })
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    mock_student_dao.return_value.get_student_by_id.assert_not_called()


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
@patch("routers.deps.StudentDAO")
def test_enforce_compliance_legacy_review_due_past(mock_student_dao):
    from datetime import datetime, timezone, timedelta
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    token = _make_token({
        "username": "testuser",
        "role": "student",
        "compliance_status": "legacy_review_due",
        "compliance_review_due_at": past,
    })
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "STUDENT_COMPLIANCE_REVIEW_REQUIRED"
    mock_student_dao.return_value.get_student_by_id.assert_not_called()


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
def test_get_auth_expired_token_returns_401():
    token = _make_token({"username": "testuser", "role": "student"}, expired=True)
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
def test_get_auth_missing_username_returns_401():
    token = _make_token({"role": "student"})  # no username
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "provisioned" in resp.json()["detail"]


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
def test_get_auth_invalid_role_returns_401():
    token = _make_token({"username": "testuser", "role": "superadmin"})
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.unit
@patch("routers.deps.SUPABASE_JWT_SECRET", TEST_SECRET)
def test_get_auth_missing_token_returns_401():
    app = _auth_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/me")
    assert resp.status_code == 401
