from typing import Optional

from pydantic import BaseModel, ConfigDict


class WaitlistStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    on_waitlist: Optional[bool] = None
    approved: Optional[bool] = None
    position: Optional[int] = None
    referral_code: Optional[str] = None
    status: Optional[str] = None
    already_approved: Optional[bool] = None
    message: Optional[str] = None


class WaitlistJoinResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: Optional[bool] = None
    position: Optional[int] = None
    referral_code: Optional[str] = None
    status: Optional[str] = None
    joined_at: Optional[str] = None
    referred_by: Optional[str] = None
    already_approved: Optional[bool] = None
    message: Optional[str] = None


class WaitlistApproveResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    waitlist_updated: bool
    teacher_updated: bool
