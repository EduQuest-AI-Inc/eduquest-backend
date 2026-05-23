import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_auth, require_active_membership, require_roles, require_student_viewer
from responses.enrollment import (
    AcceptInviteResponse,
    EnrollmentsResponse,
    EnrollResponse,
    MyPeriodItem,
    StudentProfileResponse,
    UnenrollResponse,
    VerifyPeriodResponse,
)
from responses.period import PeriodOut
from services.billing.membership_service import (
    MembershipRequiredError,
    MembershipService,
    PlanLimitExceededError,
)
from services.enrollment.enrollment_service import EnrollmentService
from services.parent.parent_service import ParentService
from services.period.period_management_service import PeriodManagementService
from services.user.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()


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

@router.post("/enroll", response_model=EnrollResponse)
def enroll(body: EnrollRequest, auth: AuthPayload = Depends(get_auth)):
    svc = EnrollmentService(jwt=auth.token)
    return svc.enroll_student(auth.sub, body.period_id, body.semester)


@router.get("/enrollments/{period_id}", response_model=EnrollmentsResponse)
def get_enrollments(period_id: str, auth: AuthPayload = Depends(require_active_membership)):
    period_mgmt = PeriodManagementService(jwt=auth.token)
    period = period_mgmt.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    svc = EnrollmentService(jwt=auth.token)
    return svc.get_enrollments_for_period(period_id)


@router.get("/student-profile/{period_id}/{user_id}", response_model=StudentProfileResponse)
def get_student_profile(period_id: str, user_id: str, auth: AuthPayload = Depends(require_active_membership)):
    period_mgmt = PeriodManagementService(jwt=auth.token)
    period = period_mgmt.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Not authorized")
    svc = EnrollmentService(jwt=auth.token)
    profile = svc.get_student_profile(period_id, user_id)
    if profile:
        return profile
    raise HTTPException(status_code=404, detail="Profile not found")


# ─── Student enrollment ───────────────────────────────────────────────────────

@router.get("/my-periods", response_model=list[MyPeriodItem])
def my_periods(
    user_id: Optional[str] = Query(None),
    auth: AuthPayload = Depends(require_student_viewer("user_id")),
):
    svc = EnrollmentService(jwt=auth.token)
    return svc.get_my_periods(user_id or auth.sub)


@router.post("/verify-period", response_model=VerifyPeriodResponse)
def verify_period(body: VerifyPeriodRequest, auth: AuthPayload = Depends(get_auth)):
    period_mgmt = PeriodManagementService(jwt=auth.token)
    user_svc = UserService()
    # Membership check uses admin to read the owner's (another user's) membership
    membership_svc = MembershipService()
    period = period_mgmt.get_period_by_id(body.period_id)
    if period:
        owner_id = period.get("owner_id")
        owner = user_svc.get_by_id(owner_id) if owner_id else None
        owner_role = owner.get("role") if owner else None
        if owner_id and owner_role in ("teacher", "parent"):
            try:
                membership_svc.check_can_add_student_to_period(
                    owner_id, owner_role, body.period_id
                )
            except MembershipRequiredError:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "This class is not currently accepting new students.",
                        "code": "OWNER_MEMBERSHIP_INACTIVE",
                    },
                )
            except PlanLimitExceededError as exc:
                raise HTTPException(
                    status_code=403,
                    detail={"error": str(exc), "code": "PLAN_LIMIT_EXCEEDED"},
                )
    svc = EnrollmentService(jwt=auth.token)
    period = svc.verify_period_id(auth.sub, body.period_id, body.allow_parent_period)
    return {"message": "Period verified and added to enrollments", "period": period}


@router.post("/unenroll", response_model=UnenrollResponse)
def unenroll(body: UnenrollRequest, auth: AuthPayload = Depends(get_auth)):
    svc = EnrollmentService(jwt=auth.token)
    return svc.unenroll_from_period(auth.sub, body.period_id)


@router.get("/student/parent-periods", response_model=list[PeriodOut])
def get_parent_periods(auth: AuthPayload = Depends(require_roles(Role.STUDENT))):
    svc = EnrollmentService(jwt=auth.token)
    return svc.get_parent_periods_for_student(auth.sub)


# ─── Parent ───────────────────────────────────────────────────────────────────

@router.post("/accept-parent-invite", response_model=AcceptInviteResponse)
def accept_parent_invite(body: AcceptInviteRequest, auth: AuthPayload = Depends(require_roles(Role.STUDENT))):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Invite code is required")
    parent_svc = ParentService(jwt=auth.token)
    result = parent_svc.accept_invite(auth.sub, code)
    return result
