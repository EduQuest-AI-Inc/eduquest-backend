from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MembershipStatus(str, Enum):
    NONE = "none"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class MembershipPlan(str, Enum):
    STARTER = "starter"
    GROWTH = "growth"
    PRO = "pro"


# Active states grant management access (create/manage classes, students, curriculum).
ACTIVE_STATES = {MembershipStatus.TRIALING, MembershipStatus.ACTIVE}

# Per-plan limits. None means unlimited.
PLAN_LIMITS: dict[MembershipPlan, dict[str, Optional[int]]] = {
    MembershipPlan.STARTER: {"class_limit": 5,  "students_per_class_limit": 20},
    MembershipPlan.GROWTH:  {"class_limit": 10, "students_per_class_limit": 20},
    MembershipPlan.PRO:     {"class_limit": 10, "students_per_class_limit": None},
}

# Marketing copy for /billing API responses (kept on the server side so the
# UI cannot accidentally drift from what's enforced server-side).
PLAN_PRICING_USD: dict[MembershipPlan, str] = {
    MembershipPlan.STARTER: "15.00",
    MembershipPlan.GROWTH:  "25.00",
    MembershipPlan.PRO:     "27.50",
}


class Membership(BaseModel):
    user_id: str
    role: str  # 'teacher' | 'parent'
    status: MembershipStatus = MembershipStatus.NONE
    plan: Optional[MembershipPlan] = None
    class_limit: Optional[int] = None
    students_per_class_limit: Optional[int] = None
    trial_started_at: Optional[str] = None
    trial_ends_at: Optional[str] = None
    reminder_sent_at: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delete_after: Optional[str] = None

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=False, mode="json")
