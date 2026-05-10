import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_auth, require_active_membership, require_roles, require_student_viewer
from data_access.period_dao import PeriodDAO
from data_access.user_dao import UserDAO
from services.billing.membership_service import (
    MembershipRequiredError,
    MembershipService,
    PlanLimitExceededError,
)
from services.enrollment.enrollment_service import EnrollmentService
from services.parent.parent_service import ParentService
from services.period.period_service import PeriodService

logger = logging.getLogger(__name__)
router = APIRouter()
service = EnrollmentService()
period_service = PeriodService()
parent_service = ParentService()
membership_service = MembershipService()
_period_dao = PeriodDAO()
_user_dao = UserDAO()


# ─── Request models ───────────────────────────────────────────────────────────

class EnrollRequest(BaseModel):
    period_id: str
    semester: str = "Fall 2025"


class VerifyPeriodRequest(BaseModel):
    period_id: str
    allow_parent_period: bool = False


class UnenrollRequest(BaseModel):
    period_id: str


class AcceptInviteRequest(BaseModel):
    code: str



# ─── Teacher-facing enrollment management ────────────────────────────────────

@router.post("/enroll")
def enroll(body: EnrollRequest, auth: AuthPayload = Depends(get_auth)):
    return service.enroll_student(auth.sub, body.period_id, body.semester)


@router.get("/enrollments/{period_id}")
def get_enrollments(period_id: str, auth: AuthPayload = Depends(require_active_membership)):
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    return service.get_enrollments_for_period(period_id)


@router.get("/student-profile/{period_id}/{user_id}")
def get_student_profile(period_id: str, user_id: str, auth: AuthPayload = Depends(require_active_membership)):
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    profile = service.get_student_profile(period_id, user_id)
    if profile:
        return profile
    raise HTTPException(status_code=404, detail="Profile not found")


# ─── Student enrollment ───────────────────────────────────────────────────────

@router.get("/my-periods")
def my_periods(
    user_id: Optional[str] = Query(None),
    auth: AuthPayload = Depends(require_student_viewer("user_id")),
):
    return period_service.get_my_periods(user_id or auth.sub)


@router.post("/verify-period")
def verify_period(body: VerifyPeriodRequest, auth: AuthPayload = Depends(get_auth)):
    # Enforce the OWNER's plan student-per-class limit at enrollment time.
    # This protects the owner from over-quota even though students aren't
    # paying — without it a parent on Starter could end up with > 20 students.
    period = _period_dao.get_period_by_id(body.period_id)
    if period:
        owner_id = period.get("owner_id")
        owner = _user_dao.get_by_id(owner_id) if owner_id else None
        owner_role = owner.get("role") if owner else None
        if owner_id and owner_role in ("teacher", "parent"):
            try:
                membership_service.check_can_add_student_to_period(
                    owner_id, owner_role, body.period_id
                )
            except MembershipRequiredError:
                # Owner's membership lapsed: do not accept new enrollments.
                # Existing students keep their assigned class access.
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "This class is not currently accepting new students.",
                        "code": "OWNER_MEMBERSHIP_INACTIVE",
                    },
                )
            except PlanLimitExceededError as e:
                raise HTTPException(
                    status_code=403,
                    detail={"error": str(e), "code": "PLAN_LIMIT_EXCEEDED"},
                )
    period = period_service.verify_period_id(auth.sub, body.period_id, body.allow_parent_period)
    return {"message": "Period verified and added to enrollments", "period": period}


@router.post("/unenroll")
def unenroll(body: UnenrollRequest, auth: AuthPayload = Depends(get_auth)):
    return period_service.unenroll_from_period(auth.sub, body.period_id)


@router.get("/student/parent-periods")
def get_parent_periods(auth: AuthPayload = Depends(require_roles(Role.STUDENT))):
    return period_service.get_parent_periods_for_student(auth.sub)


# ─── Parent ───────────────────────────────────────────────────────────────────

@router.post("/accept-parent-invite")
def accept_parent_invite(body: AcceptInviteRequest, auth: AuthPayload = Depends(require_roles(Role.STUDENT))):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Invite code is required")
    try:
        result = parent_service.accept_invite(auth.sub, code)
        return result
    except ValueError as ve:
        msg = str(ve)
        if "expired" in msg or "already been used" in msg:
            raise HTTPException(status_code=410, detail=msg)
        if "not found" in msg.lower() or "invalid" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
