from fastapi import HTTPException

from services.billing.membership_service import (
    MembershipRequiredError,
    MembershipService,
    PlanLimitExceededError,
)
from services.enrollment.enrollment_service import EnrollmentService
from services.user.user_service import UserService


def check_owner_can_accept_student(period_id: str) -> None:
    period = EnrollmentService().get_period_by_id(period_id)
    if not period:
        return

    owner_id = period.get("owner_id")
    owner = UserService().get_by_id(owner_id) if owner_id else None
    owner_role = owner.get("role") if owner else None
    if not owner_id or owner_role not in ("teacher", "parent"):
        return

    try:
        MembershipService().check_can_add_student_to_period(
            owner_id, owner_role, period_id
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
