"""Unit tests for the membership service.

Covers:
  - Trial creation is parent/teacher-only and idempotent.
  - Access evaluation flips trialing → expired once trial_ends_at passes.
  - Plan-limit enforcement (class count, students per class).
  - Stripe subscription sync maps statuses and plans correctly.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from models.membership import MembershipPlan, MembershipStatus
from services.billing.membership_service import (
    MembershipRequiredError,
    MembershipService,
    PlanLimitExceededError,
)


def _build_service(record=None, periods=None, enrollments=None):
    svc = MembershipService()
    svc.dao = MagicMock()
    svc.dao.get_by_user_id.return_value = record
    svc.dao.get_by_stripe_customer_id.return_value = None
    svc.dao.upsert.return_value = record or {}
    svc.dao.update.return_value = {}

    svc.period_dao = MagicMock()
    svc.period_dao.get_periods_by_owner_id.return_value = periods or []

    svc.enrollment_dao = MagicMock()
    svc.enrollment_dao.get_enrollments_by_period.return_value = enrollments or []

    svc.user_dao = MagicMock()
    return svc


# ── Trial creation ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_start_trial_skips_students():
    svc = _build_service()
    assert svc.start_trial_if_eligible("u1", "student") is None
    svc.dao.upsert.assert_not_called()


@pytest.mark.unit
def test_start_trial_creates_row_for_teacher():
    svc = _build_service(record=None)
    svc.dao.get_by_user_id.return_value = None
    svc.start_trial_if_eligible("teacher_1", "teacher")

    args, _ = svc.dao.upsert.call_args
    payload = args[0]
    assert payload["user_id"] == "teacher_1"
    assert payload["role"] == "teacher"
    assert payload["status"] == "trialing"
    assert payload["trial_started_at"]
    assert payload["trial_ends_at"]


@pytest.mark.unit
def test_start_trial_is_idempotent():
    existing = {"user_id": "u", "role": "parent", "status": "trialing"}
    svc = _build_service(record=existing)
    svc.start_trial_if_eligible("u", "parent")
    svc.dao.upsert.assert_not_called()


# ── Access evaluation ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_students_always_have_access():
    svc = _build_service()
    access = svc.evaluate_access("kid_1", "student")
    assert access.has_active_membership is True


@pytest.mark.unit
def test_no_membership_record_means_no_access():
    svc = _build_service(record=None)
    access = svc.evaluate_access("teacher_x", "teacher")
    assert access.has_active_membership is False
    assert access.status == MembershipStatus.NONE


@pytest.mark.unit
def test_trial_active_grants_access():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    svc = _build_service(record={
        "user_id": "u", "role": "teacher", "status": "trialing",
        "trial_ends_at": future, "plan": None,
        "class_limit": None, "students_per_class_limit": None,
    })
    access = svc.evaluate_access("u", "teacher")
    assert access.has_active_membership is True
    assert access.status == MembershipStatus.TRIALING


@pytest.mark.unit
def test_expired_trial_self_heals_to_expired():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    svc = _build_service(record={
        "user_id": "u", "role": "teacher", "status": "trialing",
        "trial_ends_at": past, "plan": None,
        "class_limit": None, "students_per_class_limit": None,
    })
    access = svc.evaluate_access("u", "teacher")
    assert access.has_active_membership is False
    assert access.status == MembershipStatus.EXPIRED
    svc.dao.update.assert_called_once_with("u", {"status": "expired"})


# ── Plan limits ────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_create_class_blocked_without_membership():
    svc = _build_service(record=None)
    with pytest.raises(MembershipRequiredError):
        svc.check_can_create_class("teacher_1", "teacher")


@pytest.mark.unit
def test_create_class_blocked_at_starter_limit():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    svc = _build_service(
        record={
            "user_id": "u", "role": "teacher", "status": "active",
            "plan": "starter", "trial_ends_at": future,
            "class_limit": 5, "students_per_class_limit": 20,
        },
        periods=[{"period_id": str(i), "status": "approved"} for i in range(5)],
    )
    with pytest.raises(PlanLimitExceededError):
        svc.check_can_create_class("u", "teacher")


@pytest.mark.unit
def test_create_class_allowed_under_limit():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    svc = _build_service(
        record={
            "user_id": "u", "role": "teacher", "status": "active",
            "plan": "starter", "trial_ends_at": future,
            "class_limit": 5, "students_per_class_limit": 20,
        },
        periods=[{"period_id": str(i), "status": "approved"} for i in range(2)],
    )
    # Should not raise.
    svc.check_can_create_class("u", "teacher")


@pytest.mark.unit
def test_pro_plan_has_unlimited_students_per_class():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    svc = _build_service(
        record={
            "user_id": "u", "role": "parent", "status": "active",
            "plan": "pro", "trial_ends_at": future,
            "class_limit": 10, "students_per_class_limit": None,
        },
        enrollments=[{"user_id": str(i)} for i in range(50)],
    )
    # Should not raise even with 50 students enrolled.
    svc.check_can_add_student_to_period("u", "parent", "p1")


@pytest.mark.unit
def test_starter_plan_blocks_21st_student():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    svc = _build_service(
        record={
            "user_id": "u", "role": "parent", "status": "active",
            "plan": "starter", "trial_ends_at": future,
            "class_limit": 5, "students_per_class_limit": 20,
        },
        enrollments=[{"user_id": str(i)} for i in range(20)],
    )
    with pytest.raises(PlanLimitExceededError):
        svc.check_can_add_student_to_period("u", "parent", "p1")


# ── Stripe sync ────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_apply_stripe_subscription_no_match_is_noop():
    svc = _build_service()
    result = svc.apply_stripe_subscription({"customer": "cus_unknown", "id": "sub_x"})
    assert result is None
    svc.dao.update.assert_not_called()


@pytest.mark.unit
def test_apply_stripe_subscription_active_growth_updates_record():
    svc = _build_service()
    svc.dao.get_by_stripe_customer_id.return_value = {"user_id": "teacher_1"}

    with patch("services.billing.membership_service._price_id_for_plan") as price_lookup:
        price_lookup.side_effect = lambda plan: {
            MembershipPlan.STARTER: "price_starter",
            MembershipPlan.GROWTH: "price_growth",
            MembershipPlan.PRO: "price_pro",
        }[plan]

        sub = {
            "id": "sub_123",
            "customer": "cus_abc",
            "status": "active",
            "current_period_end": int(
                (datetime.now(timezone.utc) + timedelta(days=30)).timestamp()
            ),
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": "price_growth"}}]},
        }
        result = svc.apply_stripe_subscription(sub)

    assert result == "teacher_1"
    args, _ = svc.dao.update.call_args
    user_id, updates = args
    assert user_id == "teacher_1"
    assert updates["plan"] == "growth"
    assert updates["status"] == "active"
    assert updates["class_limit"] == 10
    assert updates["students_per_class_limit"] == 20


@pytest.mark.unit
def test_apply_stripe_subscription_past_due_status():
    svc = _build_service()
    svc.dao.get_by_stripe_customer_id.return_value = {"user_id": "teacher_1"}
    sub = {
        "id": "sub_123",
        "customer": "cus_abc",
        "status": "past_due",
        "items": {"data": [{"price": {"id": "price_unknown"}}]},
    }
    svc.apply_stripe_subscription(sub)
    _, kwargs = svc.dao.update.call_args
    args = svc.dao.update.call_args.args
    assert args[1]["status"] == "past_due"
    assert args[1]["plan"] is None  # unknown price → no plan


# ── Membership model serialization regression ──────────────────────────────────


@pytest.mark.unit
def test_membership_to_item_updated_at_is_never_none():
    """Regression guard: updated_at=None caused PostgREST error 23502 on upsert.

    The fix: updated_at uses default_factory so it is always a non-None ISO
    string. If reverted to Optional[str] = None this test fails before the
    silent Supabase error can surface.
    """
    from models.membership import Membership
    membership = Membership(user_id="u1", role="teacher")
    item = membership.to_item()
    assert item.get("updated_at") is not None, "updated_at must not be None — Supabase NOT NULL constraint"
    assert isinstance(item["updated_at"], str)
