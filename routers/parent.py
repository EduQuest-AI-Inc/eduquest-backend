import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, require_active_membership, require_roles
from responses.parent import (
    CreateStudentProfileResponse,
    EnrollStudentResponse,
    GenerateInviteResponse,
    ParentMyPeriodsResponse,
    StudentsResponse,
)
from models.parent import CreateStudentProfileRequest
from services.billing.membership_service import MembershipRequiredError, MembershipService, PlanLimitExceededError
from services.enrollment.enrollment_service import EnrollmentService
from services.parent.parent_service import ParentService
from services.period.period_management_service import PeriodManagementService
from services.user.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_parent(auth: AuthPayload) -> None:
    if auth.role != Role.PARENT:
        raise HTTPException(status_code=403, detail="Requires parent role")


@router.get("/my-periods", response_model=ParentMyPeriodsResponse)
def my_periods(auth: AuthPayload = Depends(require_roles(Role.PARENT))):
    svc = PeriodManagementService(jwt=auth.token)
    periods = svc.get_periods_by_owner(auth.sub)
    return {"periods": periods}


@router.post("/generate-invite", status_code=201, response_model=GenerateInviteResponse)
def generate_invite(auth: AuthPayload = Depends(require_active_membership)):
    _ensure_parent(auth)
    svc = ParentService(jwt=auth.token)
    return svc.generate_invite(auth.sub)


@router.get("/students", response_model=StudentsResponse)
def get_students(auth: AuthPayload = Depends(require_active_membership)):
    _ensure_parent(auth)
    svc = ParentService(jwt=auth.token)
    students = svc.get_linked_students(auth.sub)
    return {"students": students}


class EnrollStudentRequest(BaseModel):
    student_id: str
    period_id: str


@router.post("/enroll-student", status_code=200, response_model=EnrollStudentResponse)
def enroll_student(
    body: EnrollStudentRequest,
    auth: AuthPayload = Depends(require_active_membership),
):
    _ensure_parent(auth)

    enrollment_svc = EnrollmentService(jwt=auth.token)
    enrollment_svc.validate_parent_enrollment_preconditions(
        auth.sub, body.student_id, body.period_id
    )

    period_mgmt = PeriodManagementService(jwt=auth.token)
    user_svc = UserService(jwt=auth.token)
    # Membership check uses admin to read owner's (another user's) membership
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

    result = enrollment_svc.verify_period_id(
        body.student_id, body.period_id, allow_parent_period=True
    )
    return {"message": "Student enrolled in class", "period": result}


@router.post("/create-student-profile", status_code=201, response_model=CreateStudentProfileResponse)
def create_student_profile(
    payload: CreateStudentProfileRequest,
    auth: AuthPayload = Depends(require_active_membership),
):
    _ensure_parent(auth)
    svc = ParentService(jwt=auth.token)
    result = svc.create_student_profile(
        auth.sub, payload.name, payload.grade, payload.interests
    )
    return result
