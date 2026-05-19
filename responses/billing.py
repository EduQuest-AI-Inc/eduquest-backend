from typing import Optional

from pydantic import BaseModel, ConfigDict


class PlanOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    price_usd: float
    interval: str
    class_limit: Optional[int] = None
    students_per_class_limit: Optional[int] = None


class MembershipResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    status: str
    plan: Optional[str] = None
    has_active_membership: bool
    trial_started_at: Optional[str] = None
    trial_ends_at: Optional[str] = None
    class_limit: Optional[int] = None
    students_per_class_limit: Optional[int] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    stripe_customer_id_present: bool
    available_plans: list[PlanOut] = []


class CheckoutSessionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str


class PortalSessionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str


class WebhookResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    received: bool
    handled: Optional[bool] = None
