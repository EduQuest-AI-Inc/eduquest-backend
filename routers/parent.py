import logging

from fastapi import APIRouter, Depends, HTTPException

from routers.deps import AuthPayload, Role, require_active_membership, require_roles
from services.parent.parent_service import ParentService
from services.period.period_management_service import PeriodManagementService

logger = logging.getLogger(__name__)
router = APIRouter()
parent_service = ParentService()
period_management_service = PeriodManagementService()


def _ensure_parent(auth: AuthPayload) -> None:
    if auth.role != Role.PARENT:
        raise HTTPException(status_code=403, detail="Requires parent role")


@router.get("/my-periods")
def my_periods(auth: AuthPayload = Depends(require_roles(Role.PARENT))):
    # Listing remains open even if membership lapses; gate is on management.
    periods = period_management_service.get_periods_by_owner(auth.sub)
    return {"periods": periods}


@router.post("/generate-invite", status_code=201)
def generate_invite(auth: AuthPayload = Depends(require_active_membership)):
    _ensure_parent(auth)
    return parent_service.generate_invite(auth.sub)


@router.get("/students")
def get_students(auth: AuthPayload = Depends(require_active_membership)):
    _ensure_parent(auth)
    students = parent_service.get_linked_students(auth.sub)
    return {"students": students}
