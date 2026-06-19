import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_auth, require_roles
from responses.waitlist import WaitlistApproveResponse, WaitlistJoinResponse, WaitlistStatusResponse
from services.waitlist.waitlist_service import WaitlistService

router = APIRouter()
svc = WaitlistService()

ADMIN_IDS = set(filter(None, os.getenv("ADMIN_USER_IDS", "").split(",")))


@router.get("/status", response_model=WaitlistStatusResponse)
def get_waitlist_status(auth: AuthPayload = Depends(get_auth)):
    return svc.get_status(auth.sub)


class JoinRequest(BaseModel):
    referralCode: Optional[str] = None
    referral_code: Optional[str] = None


@router.post("/join", response_model=WaitlistJoinResponse)
def join_pilot_waitlist(
    body: JoinRequest,
    auth: AuthPayload = Depends(get_auth),
):
    referral_code = body.referralCode or body.referral_code
    return svc.join(auth.sub, referral_code)


@router.post("/approve/{user_id}", response_model=WaitlistApproveResponse)
def approve_teacher(
    user_id: str,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER)),
):
    if auth.sub not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = svc.approve(user_id)
    if result.get("success"):
        return result
    raise HTTPException(status_code=400, detail="Failed to approve teacher")
