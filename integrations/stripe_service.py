"""Thin Stripe SDK wrapper.

Centralises API key configuration so we never sprinkle stripe.api_key = ... in
multiple modules and so tests can monkeypatch a single import path.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import stripe

logger = logging.getLogger(__name__)

_initialized = False


def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        # Don't crash imports during dev / CI without billing env. The first
        # actual API call will surface a clearer 500.
        logger.warning("STRIPE_SECRET_KEY is not set — Stripe calls will fail.")
    stripe.api_key = api_key or ""
    _initialized = True


def get_stripe():
    _ensure_initialized()
    return stripe


def get_or_create_customer(*, user_id: str, email: str, name: Optional[str], existing_id: Optional[str]) -> str:
    """Idempotently obtain a Stripe Customer for the given user."""
    s = get_stripe()
    if existing_id:
        try:
            cust = s.Customer.retrieve(existing_id)
            if not cust.get("deleted"):  # type: ignore[attr-defined]
                return existing_id
        except stripe.InvalidRequestError:
            # Customer was deleted on Stripe side — fall through and recreate.
            pass

    cust = s.Customer.create(
        email=email,
        name=name,  # type: ignore[arg-type]
        metadata={"eduquest_user_id": user_id},
    )
    return cust["id"]


def create_subscription_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    user_id: str,
) -> str:
    """Create a Stripe-hosted Checkout Session for a recurring subscription."""
    s = get_stripe()
    session = s.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,
        allow_promotion_codes=True,
        payment_method_collection="if_required",
        metadata={"eduquest_user_id": user_id},
    )
    return session["url"]


def create_billing_portal_session(*, customer_id: str, return_url: str) -> str:
    s = get_stripe()
    portal = s.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return portal["url"]


def cancel_subscription_immediately(subscription_id: str) -> None:
    """Cancel a Stripe subscription immediately (no end-of-period grace)."""
    s = get_stripe()
    s.Subscription.cancel(subscription_id)


def construct_webhook_event(payload: bytes, signature: str, secret: str):
    """Verify a Stripe webhook signature; raises stripe.SignatureVerificationError on bad sig."""
    s = get_stripe()
    return s.Webhook.construct_event(payload, signature, secret)
