"""
Unit tests for routers/deps.py — require_student_viewer dependency.

A fresh minimal FastAPI app is built per test so that the ParentService /
EnrollmentService instances captured inside the closure can be swapped out
via patch before require_student_viewer() is called.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from routers.deps import require_student_viewer, get_auth, AuthPayload, Role


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
