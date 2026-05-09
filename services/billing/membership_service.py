"""
Membership lifecycle service.

Owns:
  - Trial creation (no card collected, 14 days from creation).
  - Status accessors that the dependency-injection layer uses to gate routes.
  - Plan limit enforcement (active classes per owner, students per class).
  - Stripe webhook → local membership sync.

Compliance notes:
  - We never log Stripe payment instrument data. Only customer/subscription IDs
    leave Stripe and land here, and even those stay server-side.
  - audit_log() is intentionally a thin logger.info wrapper so future SOC 2
    rotation/retention work has a single seam to upgrade.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from data_access.enrollment_dao import EnrollmentDAO
from data_access.membership_dao import MembershipDAO
from data_access.period_dao import PeriodDAO
from data_access.user_dao import UserDAO
from models.membership import (
    ACTIVE_STATES,
    PLAN_LIMITS,
    PLAN_PRICING_USD,
    Membership,
    MembershipPlan,
    MembershipStatus,
)

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14
REMINDER_LEAD_DAYS = 7

# Hard list of roles that ever have a membership row. Students do not.
MEMBERSHIP_ELIGIBLE_ROLES = ("teacher", "parent")


@dataclass(frozen=True)
class MembershipAccess:
    """Result of evaluating whether an owner may manage classes."""
    user_id: str
    role: str
    has_active_membership: bool
    status: MembershipStatus
    plan: Optional[MembershipPlan]
    trial_ends_at: Optional[str]
    class_limit: Optional[int]
    students_per_class_limit: Optional[int]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _audit_log(action: str, user_id: str, **meta: Any) -> None:
    logger.info("billing.audit action=%s user_id=%s meta=%s", action, user_id, meta)


def _price_id_for_plan(plan: MembershipPlan) -> Optional[str]:
    env_map = {
        MembershipPlan.STARTER: "STRIPE_PRICE_STARTER",
        MembershipPlan.GROWTH:  "STRIPE_PRICE_GROWTH",
        MembershipPlan.PRO:     "STRIPE_PRICE_PRO",
    }
    return os.getenv(env_map[plan])


def _plan_for_price_id(price_id: Optional[str]) -> Optional[MembershipPlan]:
    if not price_id:
        return None
    for plan in MembershipPlan:
        if _price_id_for_plan(plan) == price_id:
            return plan
    return None


class MembershipService:
    def __init__(self) -> None:
        self.dao = MembershipDAO()
        self.user_dao = UserDAO()
        self.period_dao = PeriodDAO()
        self.enrollment_dao = EnrollmentDAO()

    # ── Read ────────────────────────────────────────────────────────────────

    def get_membership(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.dao.get_by_user_id(user_id)

    def evaluate_access(self, user_id: str, role: str) -> MembershipAccess:
        """Return a snapshot describing whether this user may manage classes."""
        if role not in MEMBERSHIP_ELIGIBLE_ROLES:
            # Students are never gated.
            return MembershipAccess(
                user_id=user_id,
                role=role,
                has_active_membership=True,
                status=MembershipStatus.ACTIVE,
                plan=None,
                trial_ends_at=None,
                class_limit=None,
                students_per_class_limit=None,
            )

        record = self.dao.get_by_user_id(user_id)
        if not record:
            return MembershipAccess(
                user_id=user_id, role=role,
                has_active_membership=False,
                status=MembershipStatus.NONE,
                plan=None, trial_ends_at=None,
                class_limit=None, students_per_class_limit=None,
            )

        status = MembershipStatus(record["status"])
        # Self-heal: if a trial has elapsed without paying, treat as expired.
        trial_end_dt = _parse_iso(record.get("trial_ends_at"))
        if status == MembershipStatus.TRIALING and trial_end_dt and trial_end_dt <= _now():
            self._mark_trial_expired(user_id)
            status = MembershipStatus.EXPIRED

        plan_value = record.get("plan")
        plan = MembershipPlan(plan_value) if plan_value else None

        return MembershipAccess(
            user_id=user_id,
            role=role,
            has_active_membership=status in ACTIVE_STATES,
            status=status,
            plan=plan,
            trial_ends_at=record.get("trial_ends_at"),
            class_limit=record.get("class_limit"),
            students_per_class_limit=record.get("students_per_class_limit"),
        )

    def membership_view(self, user_id: str, role: str) -> Dict[str, Any]:
        """JSON-friendly view exposed by GET /billing/membership."""
        access = self.evaluate_access(user_id, role)
        record = self.dao.get_by_user_id(user_id) or {}
        return {
            "role": role,
            "status": access.status.value,
            "plan": access.plan.value if access.plan else None,
            "has_active_membership": access.has_active_membership,
            "trial_started_at": record.get("trial_started_at"),
            "trial_ends_at": access.trial_ends_at,
            "class_limit": access.class_limit,
            "students_per_class_limit": access.students_per_class_limit,
            "current_period_end": record.get("current_period_end"),
            "cancel_at_period_end": record.get("cancel_at_period_end", False),
            "stripe_customer_id_present": bool(record.get("stripe_customer_id")),
            "available_plans": self._plan_catalog(),
        }

    @staticmethod
    def _plan_catalog() -> list[Dict[str, Any]]:
        plans: list[Dict[str, Any]] = []
        for plan in MembershipPlan:
            limits = PLAN_LIMITS[plan]
            plans.append({
                "id": plan.value,
                "price_usd": PLAN_PRICING_USD[plan],
                "interval": "month",
                "class_limit": limits["class_limit"],
                "students_per_class_limit": limits["students_per_class_limit"],
            })
        return plans

    # ── Write: trial & lifecycle ────────────────────────────────────────────

    def start_trial_if_eligible(self, user_id: str, role: str) -> Optional[Dict[str, Any]]:
        """Create a 14-day trial row for parents/teachers. Idempotent."""
        if role not in MEMBERSHIP_ELIGIBLE_ROLES:
            return None
        existing = self.dao.get_by_user_id(user_id)
        if existing:
            return existing

        now = _now()
        trial_ends = now + timedelta(days=TRIAL_DAYS)
        membership = Membership(
            user_id=user_id,
            role=role,
            status=MembershipStatus.TRIALING,
            trial_started_at=_iso(now),
            trial_ends_at=_iso(trial_ends),
        )
        record = self.dao.upsert(membership.to_item())
        _audit_log("trial_started", user_id, role=role, trial_ends_at=_iso(trial_ends))
        return record

    def _mark_trial_expired(self, user_id: str) -> None:
        self.dao.update(user_id, {"status": MembershipStatus.EXPIRED.value})
        _audit_log("trial_expired", user_id)

    def mark_reminder_sent(self, user_id: str) -> None:
        self.dao.update(user_id, {"reminder_sent_at": _iso(_now())})

    # ── Write: Stripe sync ──────────────────────────────────────────────────

    def attach_stripe_customer(self, user_id: str, customer_id: str) -> None:
        self.dao.update(user_id, {"stripe_customer_id": customer_id})

    def apply_stripe_subscription(self, subscription: Any) -> Optional[str]:
        """Mirror a Stripe Subscription object into the local membership row.

        Returns the user_id whose membership was synced, or None if we couldn't
        locate the customer. Treated as a no-op when the customer isn't ours.
        """
        customer_id = subscription.get("customer")
        if not customer_id:
            return None
        record = self.dao.get_by_stripe_customer_id(customer_id)
        if not record:
            logger.info(
                "stripe.subscription.no_membership_for_customer customer_id=%s",
                customer_id,
            )
            return None

        sub_id = subscription.get("id")
        items = (subscription.get("items") or {}).get("data") or []
        price_id: Optional[str] = None
        if items:
            price_id = ((items[0].get("price") or {}).get("id"))

        plan = _plan_for_price_id(price_id)
        limits = PLAN_LIMITS[plan] if plan else {"class_limit": None, "students_per_class_limit": None}

        status_str = subscription.get("status") or "active"
        membership_status = self._stripe_status_to_membership(status_str)

        cpe = subscription.get("current_period_end")
        cpe_iso = (
            datetime.fromtimestamp(cpe, tz=timezone.utc).isoformat()
            if isinstance(cpe, (int, float))
            else None
        )

        updates: Dict[str, Any] = {
            "stripe_subscription_id": sub_id,
            "stripe_price_id": price_id,
            "plan": plan.value if plan else None,
            "class_limit": limits["class_limit"],
            "students_per_class_limit": limits["students_per_class_limit"],
            "status": membership_status.value,
            "current_period_end": cpe_iso,
            "cancel_at_period_end": bool(subscription.get("cancel_at_period_end", False)),
        }
        self.dao.update(record["user_id"], updates)
        _audit_log(
            "stripe_subscription_synced",
            record["user_id"],
            stripe_subscription_id=sub_id,
            status=membership_status.value,
            plan=plan.value if plan else None,
        )
        return record["user_id"]

    def mark_subscription_canceled(self, subscription_id: str) -> Optional[str]:
        record = self.dao.get_by_stripe_subscription_id(subscription_id)
        if not record:
            return None
        self.dao.update(record["user_id"], {
            "status": MembershipStatus.CANCELED.value,
            "cancel_at_period_end": True,
        })
        _audit_log("stripe_subscription_canceled", record["user_id"], subscription_id=subscription_id)
        return record["user_id"]

    @staticmethod
    def _stripe_status_to_membership(stripe_status: str) -> MembershipStatus:
        mapping = {
            "trialing": MembershipStatus.TRIALING,
            "active": MembershipStatus.ACTIVE,
            "past_due": MembershipStatus.PAST_DUE,
            "unpaid": MembershipStatus.PAST_DUE,
            "incomplete": MembershipStatus.PAST_DUE,
            "incomplete_expired": MembershipStatus.EXPIRED,
            "canceled": MembershipStatus.CANCELED,
            "paused": MembershipStatus.PAST_DUE,
        }
        return mapping.get(stripe_status, MembershipStatus.ACTIVE)

    # ── Plan limit enforcement ─────────────────────────────────────────────

    def assert_can_create_class(self, user_id: str, role: str) -> None:
        access = self.evaluate_access(user_id, role)
        if not access.has_active_membership:
            raise MembershipRequiredError(access)
        if access.class_limit is None:
            return  # active trial with no enforced limit yet
        owned = self.period_dao.get_periods_by_owner_id(user_id) or []
        active = [p for p in owned if p.get("status") not in ("deleted",)]
        if len(active) >= access.class_limit:
            raise PlanLimitExceededError(
                f"Your {access.plan.value if access.plan else 'current'} plan allows "
                f"up to {access.class_limit} active classes. "
                f"Upgrade to add more.",
            )

    def assert_can_add_student_to_period(self, owner_id: str, role: str, period_id: str) -> None:
        access = self.evaluate_access(owner_id, role)
        if not access.has_active_membership:
            raise MembershipRequiredError(access)
        if access.students_per_class_limit is None:
            return  # unlimited
        existing = self.enrollment_dao.get_enrollments_by_period(period_id) or []
        if len(existing) >= access.students_per_class_limit:
            raise PlanLimitExceededError(
                f"Your plan allows up to {access.students_per_class_limit} "
                f"students per class.",
            )


class MembershipRequiredError(Exception):
    def __init__(self, access: MembershipAccess) -> None:
        self.access = access
        super().__init__("Membership required")


class PlanLimitExceededError(Exception):
    """Raised when the owner has hit a per-plan ceiling."""
