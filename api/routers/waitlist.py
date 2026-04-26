from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from routes.waitlist.WaitlistService import WaitlistService

router = APIRouter()
svc = WaitlistService()


@router.get("/status")
def get_waitlist_status(auth: AuthPayload = Depends(get_auth)):
    try:
        return svc.get_status(auth.sub)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get waitlist status")


class JoinRequest(BaseModel):
    referralCode: Optional[str] = None
    referral_code: Optional[str] = None


@router.post("/join")
def join_pilot_waitlist(
    body: JoinRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        referral_code = body.referralCode or body.referral_code
        return svc.join(auth.sub, referral_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to join waitlist")


@router.post("/approve/{user_id}")
def approve_teacher(user_id: str, auth: AuthPayload = Depends(get_auth)):
    # TODO: add admin role check
    try:
        result = svc.approve(user_id)
        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail="Failed to approve teacher")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to approve teacher")
