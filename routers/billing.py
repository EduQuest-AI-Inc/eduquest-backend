"""
Billing endpoints (Stripe-backed memberships for parents/teachers).

Routes:
  GET  /billing/membership            — current user's status, plan, limits
  POST /billing/checkout-session      — create Stripe Checkout (subscription)
  POST /billing/portal-session        — open Stripe Billing Portal
  POST /billing/webhook               — Stripe → server sync

Compliance:
  - Students never reach this router (require_roles enforces). Membership data
    is parent/teacher-only and contains no payment instrument data; only
    Stripe customer/subscription IDs are persisted.
  - Webhooks verify Stripe signatures; never trust the body otherwise.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from integrations import stripe_service
from models.membership import MembershipPlan
from routers.deps import AuthPayload, Role, require_roles
from services.billing.membership_service import MembershipService
from services.user.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()

_membership_service = MembershipService()
_user_service = UserService()


def _require_role_value(auth: AuthPayload) -> str:
    return auth.role.value if hasattr(auth.role, "value") else str(auth.role)


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/membership")
def get_membership(
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    return _membership_service.membership_view(auth.sub, _require_role_value(auth))


# ── Checkout ───────────────────────────────────────────────────────────────────

class _CheckoutRequest(BaseModel):
    plan: str  # "starter" | "growth" | "pro"


@router.post("/checkout-session")
def create_checkout_session(
    body: _CheckoutRequest,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    try:
        plan = MembershipPlan(body.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown plan")

    price_env_map = {
        MembershipPlan.STARTER: "STRIPE_PRICE_STARTER",
        MembershipPlan.GROWTH:  "STRIPE_PRICE_GROWTH",
        MembershipPlan.PRO:     "STRIPE_PRICE_PRO",
    }
    price_id = os.getenv(price_env_map[plan])
    if not price_id:
        raise HTTPException(status_code=500, detail="Plan price is not configured")

    user = _user_service.get_by_id(auth.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    record = _membership_service.get_membership(auth.sub) or {}
    customer_id = stripe_service.get_or_create_customer(
        user_id=auth.sub,
        email=user.get("email", ""),
        name=f'{user.get("first_name", "")} {user.get("last_name", "")}'.strip() or None,
        existing_id=record.get("stripe_customer_id"),
    )
    if record.get("stripe_customer_id") != customer_id:
        _membership_service.attach_stripe_customer(auth.sub, customer_id)

    base = (os.getenv("FRONTEND_BASE_URL") or "http://localhost:3000").rstrip("/")
    success_url = f"{base}/billing?checkout=success"
    cancel_url = f"{base}/billing?checkout=cancelled"

    try:
        url = stripe_service.create_subscription_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            user_id=auth.sub,
        )
    except Exception as e:  # stripe.error.* surfaces through here
        logger.error("Stripe checkout creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Could not start checkout")

    return {"url": url}


# ── Billing portal ─────────────────────────────────────────────────────────────

@router.post("/portal-session")
def create_portal_session(
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    record = _membership_service.get_membership(auth.sub) or {}
    customer_id: Optional[str] = record.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on file. Subscribe first.")

    return_url = os.getenv("STRIPE_PORTAL_RETURN_URL") or (
        ((os.getenv("FRONTEND_BASE_URL") or "http://localhost:3000").rstrip("/")) + "/billing"
    )

    try:
        url = stripe_service.create_billing_portal_session(
            customer_id=customer_id,
            return_url=return_url,
        )
    except Exception as e:
        logger.error("Stripe portal creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Could not open billing portal")
    return {"url": url}


# ── Webhook ────────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not set; rejecting webhook")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.construct_webhook_event(payload, signature, secret)
    except Exception as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type: str = getattr(event, "type", "") or ""
    data = getattr(getattr(event, "data", None), "object", None) or {}
    logger.info("stripe.webhook event_type=%s id=%s", event_type, getattr(event, "id", None))

    try:
        if event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.trial_will_end",
        ):
            _membership_service.apply_stripe_subscription(data)
        elif event_type == "customer.subscription.deleted":
            sub_id = data.get("id")
            if sub_id:
                _membership_service.mark_subscription_canceled(sub_id)
        elif event_type == "checkout.session.completed":
            # Subscription mode: pull subscription id and sync.
            sub_id = data.get("subscription")
            if sub_id:
                stripe = stripe_service.get_stripe()
                sub = stripe.Subscription.retrieve(sub_id)
                _membership_service.apply_stripe_subscription(sub)
        elif event_type == "invoice.payment_failed":
            sub_id = data.get("subscription")
            if sub_id:
                stripe = stripe_service.get_stripe()
                sub = stripe.Subscription.retrieve(sub_id)
                _membership_service.apply_stripe_subscription(sub)
    except Exception as e:
        logger.error("Stripe webhook handler failed: %s", e, exc_info=True)
        # Return 200 so Stripe doesn't retry forever for application bugs we
        # need to fix on our side; we'll surface failures via logs/alerting.
        return {"received": True, "handled": False}

    return {"received": True}
