"""Tests for the require_active_membership FastAPI dependency.

Constructs a tiny FastAPI app that mounts only the dependency and asserts
the structured 403 contract the frontend depends on.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from routers.deps import AuthPayload, Role, get_auth, require_active_membership


def _make_app():
    app = FastAPI()

    @app.get("/protected")
    def protected(auth: AuthPayload = Depends(require_active_membership)):
        return {"sub": auth.sub}

    return app


@pytest.fixture
def app():
    return _make_app()


def _override_auth(app, role: Role, sub="user-1"):
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub=sub, role=role, token="t",
    )


@pytest.mark.api
def test_student_role_blocked_with_owner_role_required(app):
    _override_auth(app, Role.STUDENT)
    with TestClient(app) as c:
        resp = c.get("/protected")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "OWNER_ROLE_REQUIRED"


@pytest.mark.api
def test_teacher_without_membership_blocked(app):
    _override_auth(app, Role.TEACHER)
    with patch(
        "services.billing.membership_service.MembershipService"
    ) as svc_cls:
        svc = MagicMock()
        access = MagicMock()
        access.has_active_membership = False
        access.status.value = "expired"
        access.trial_ends_at = "2026-04-01T00:00:00+00:00"
        svc.evaluate_access.return_value = access
        svc_cls.return_value = svc

        with TestClient(app) as c:
            resp = c.get("/protected")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "MEMBERSHIP_REQUIRED"
    assert detail["status"] == "expired"


@pytest.mark.api
def test_parent_with_active_trial_passes(app):
    _override_auth(app, Role.PARENT)
    with patch(
        "services.billing.membership_service.MembershipService"
    ) as svc_cls:
        svc = MagicMock()
        access = MagicMock()
        access.has_active_membership = True
        access.status.value = "trialing"
        access.trial_ends_at = (
            datetime.now(timezone.utc) + timedelta(days=10)
        ).isoformat()
        svc.evaluate_access.return_value = access
        svc_cls.return_value = svc

        with TestClient(app) as c:
            resp = c.get("/protected")
    assert resp.status_code == 200
