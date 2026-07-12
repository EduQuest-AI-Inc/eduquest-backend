"""API-level tests for /billing routes.

These tests exercise the FastAPI route definitions directly. They patch the
billing service / Stripe layer so no Stripe calls leave the test process.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.deps import AuthPayload, Role, get_auth


@pytest.fixture
def teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-1", role=Role.TEACHER, token="t",
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def parent_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="parent-1", role=Role.PARENT, token="t",
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def student_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="student-1", role=Role.STUDENT, token="t",
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── /billing/membership ────────────────────────────────────────────────────────


@pytest.mark.api
def test_membership_status_requires_owner_role(student_client):
    resp = student_client.get("/billing/membership")
    assert resp.status_code == 403


@pytest.mark.api
def test_membership_status_returns_view_for_teacher(teacher_client):
    fake_view = {
        "role": "teacher",
        "status": "trialing",
        "plan": None,
        "has_active_membership": True,
        "trial_ends_at": "2026-06-01T00:00:00+00:00",
        "trial_started_at": "2026-05-01T00:00:00+00:00",
        "class_limit": None,
        "students_per_class_limit": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
        "stripe_customer_id_present": False,
        "available_plans": [],
    }
    mock_svc = MagicMock()
    mock_svc.membership_view.return_value = fake_view
    with patch("routers.billing.MembershipService", return_value=mock_svc):
        resp = teacher_client.get("/billing/membership")
    assert resp.status_code == 200
    assert resp.json()["status"] == "trialing"


# ── /billing/checkout-session ──────────────────────────────────────────────────


@pytest.mark.api
def test_checkout_rejects_unknown_plan(teacher_client):
    resp = teacher_client.post("/billing/checkout-session", json={"plan": "platinum"})
    assert resp.status_code == 400


@pytest.mark.api
def test_checkout_requires_price_env(teacher_client, monkeypatch):
    monkeypatch.delenv("STRIPE_PRICE_STARTER", raising=False)
    resp = teacher_client.post("/billing/checkout-session", json={"plan": "starter"})
    assert resp.status_code == 500


@pytest.mark.api
def test_checkout_creates_stripe_session(teacher_client, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")

    mock_user_svc = MagicMock()
    mock_user_svc.get_by_id.return_value = {
        "user_id": "teacher-1", "email": "t@eduquestai.org",
        "first_name": "T", "last_name": "Acher",
    }
    mock_membership_svc = MagicMock()
    mock_membership_svc.get_membership.return_value = None

    with patch("routers.billing.UserService", return_value=mock_user_svc), \
         patch("routers.billing.MembershipService", return_value=mock_membership_svc), \
         patch("routers.billing.stripe_service") as stripe:
        stripe.get_or_create_customer.return_value = "cus_123"
        stripe.create_subscription_checkout_session.return_value = "https://checkout.stripe.com/abc"

        resp = teacher_client.post("/billing/checkout-session", json={"plan": "starter"})

    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://checkout.stripe.com/")
    stripe.get_or_create_customer.assert_called_once()
    mock_membership_svc.attach_stripe_customer.assert_called_once_with("teacher-1", "cus_123")


def _checkout_with_origin(client, monkeypatch, origin):
    """POST checkout with the given origin; return the kwargs passed to Stripe."""
    monkeypatch.setenv("STRIPE_PRICE_STARTER", "price_starter")
    mock_user_svc = MagicMock()
    mock_user_svc.get_by_id.return_value = {
        "user_id": "teacher-1", "email": "t@eduquestai.org",
        "first_name": "T", "last_name": "Acher",
    }
    mock_membership_svc = MagicMock()
    mock_membership_svc.get_membership.return_value = None

    with patch("routers.billing.UserService", return_value=mock_user_svc), \
         patch("routers.billing.MembershipService", return_value=mock_membership_svc), \
         patch("routers.billing.stripe_service") as stripe:
        stripe.get_or_create_customer.return_value = "cus_123"
        stripe.create_subscription_checkout_session.return_value = "https://checkout.stripe.com/abc"
        body = {"plan": "starter"}
        if origin is not None:
            body["origin"] = origin
        resp = client.post("/billing/checkout-session", json=body)
    assert resp.status_code == 200
    return stripe.create_subscription_checkout_session.call_args.kwargs


@pytest.mark.api
def test_checkout_uses_allowlisted_origin(teacher_client, monkeypatch):
    kwargs = _checkout_with_origin(teacher_client, monkeypatch, "https://eduquestai.org")
    assert kwargs["success_url"] == "https://eduquestai.org/billing?checkout=success"
    assert kwargs["cancel_url"] == "https://eduquestai.org/billing?checkout=cancelled"


@pytest.mark.api
def test_checkout_rejects_unknown_origin(teacher_client, monkeypatch):
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://eduquestai.org")
    kwargs = _checkout_with_origin(teacher_client, monkeypatch, "https://evil.com")
    assert kwargs["success_url"].startswith("https://eduquestai.org/")
    assert "evil.com" not in kwargs["success_url"]


@pytest.mark.api
def test_checkout_falls_back_when_no_origin(teacher_client, monkeypatch):
    monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
    kwargs = _checkout_with_origin(teacher_client, monkeypatch, None)
    assert kwargs["success_url"] == "https://eduquestai.org/billing?checkout=success"


# ── /billing/portal-session ────────────────────────────────────────────────────


@pytest.mark.api
def test_portal_rejects_when_no_customer(teacher_client):
    mock_svc = MagicMock()
    mock_svc.get_membership.return_value = None
    with patch("routers.billing.MembershipService", return_value=mock_svc):
        resp = teacher_client.post("/billing/portal-session")
    assert resp.status_code == 400


@pytest.mark.api
def test_portal_returns_url(teacher_client):
    mock_svc = MagicMock()
    mock_svc.get_membership.return_value = {"stripe_customer_id": "cus_123"}
    with patch("routers.billing.MembershipService", return_value=mock_svc), \
         patch("routers.billing.stripe_service") as stripe:
        stripe.create_billing_portal_session.return_value = "https://portal.stripe.com/abc"
        resp = teacher_client.post("/billing/portal-session")
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://portal.stripe.com/")


@pytest.mark.api
def test_portal_return_url_uses_allowlisted_origin(teacher_client, monkeypatch):
    monkeypatch.delenv("STRIPE_PORTAL_RETURN_URL", raising=False)
    mock_svc = MagicMock()
    mock_svc.get_membership.return_value = {"stripe_customer_id": "cus_123"}
    with patch("routers.billing.MembershipService", return_value=mock_svc), \
         patch("routers.billing.stripe_service") as stripe:
        stripe.create_billing_portal_session.return_value = "https://portal.stripe.com/abc"
        resp = teacher_client.post(
            "/billing/portal-session", json={"origin": "https://eduquestai.org"},
        )
    assert resp.status_code == 200
    kwargs = stripe.create_billing_portal_session.call_args.kwargs
    assert kwargs["return_url"] == "https://eduquestai.org/billing"


# ── /billing/webhook ────────────────────────────────────────────────────────────


@pytest.mark.api
def test_webhook_rejects_when_secret_missing(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    with TestClient(app) as c:
        resp = c.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert resp.status_code == 500


@pytest.mark.api
def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    with patch("routers.billing.stripe_service") as stripe:
        stripe.construct_webhook_event.side_effect = Exception("bad sig")
        with TestClient(app) as c:
            resp = c.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert resp.status_code == 400


@pytest.mark.api
def test_webhook_routes_subscription_updated(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    fake_data_obj = {"id": "sub_1", "customer": "cus_1", "status": "active",
                     "items": {"data": [{"price": {"id": "p"}}]}}
    fake_event = MagicMock()
    fake_event.id = "evt_1"
    fake_event.type = "customer.subscription.updated"
    fake_event.data.object = fake_data_obj
    with patch("routers.billing.stripe_service") as stripe, \
         patch("routers.billing._webhook_membership_service") as svc:
        stripe.construct_webhook_event.return_value = fake_event
        with TestClient(app) as c:
            resp = c.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert resp.status_code == 200
    svc.apply_stripe_subscription.assert_called_once()


@pytest.mark.api
def test_webhook_subscription_deleted(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    fake_data_obj = {"id": "sub_1"}
    fake_event = MagicMock()
    fake_event.id = "evt_1"
    fake_event.type = "customer.subscription.deleted"
    fake_event.data.object = fake_data_obj
    with patch("routers.billing.stripe_service") as stripe, \
         patch("routers.billing._webhook_membership_service") as svc:
        stripe.construct_webhook_event.return_value = fake_event
        with TestClient(app) as c:
            resp = c.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert resp.status_code == 200
    svc.mark_subscription_canceled.assert_called_once_with("sub_1")
