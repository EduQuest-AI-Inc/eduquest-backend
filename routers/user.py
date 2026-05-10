import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth, require_student_viewer
from data_access.parent_dao import ParentDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.user_dao import UserDAO
from services.period.period_service import PeriodService
from services.user.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter()
user_service = UserService()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
parent_dao = ParentDAO()
user_dao = UserDAO()
period_service_u = PeriodService()

_ROLE_FETCHERS = {
    "student": lambda uid: student_dao.get_student_by_id(uid),
    "teacher": lambda uid: teacher_dao.get_teacher_by_id(uid),
    "parent":  lambda uid: parent_dao.get_parent_by_id(uid),
}


def _fetch_user_profile(user_id: str) -> Optional[dict]:
    user = user_dao.get_by_id(user_id)
    if not user:
        return None
    role = user.get("role") or ""
    fetcher = _ROLE_FETCHERS.get(role)
    if not fetcher:
        return None
    profile = fetcher(user_id)
    if not profile:
        return None
    profile["role"] = role
    if role == "teacher":
        profile.setdefault("pilot_approved", False)
        profile.pop("canvas_api_key", None)
    if role in ("teacher", "parent"):
        # Inline a compact membership snapshot so the dashboard can decide
        # whether to gate management UI without a second round trip.
        try:
            from services.billing.membership_service import MembershipService
            access = MembershipService().evaluate_access(user_id, role)
            profile["membership"] = {
                "status": access.status.value,
                "plan": access.plan.value if access.plan else None,
                "has_active_membership": access.has_active_membership,
                "trial_ends_at": access.trial_ends_at,
                "class_limit": access.class_limit,
                "students_per_class_limit": access.students_per_class_limit,
            }
        except Exception:
            profile["membership"] = {
                "status": "none",
                "plan": None,
                "has_active_membership": False,
                "trial_ends_at": None,
                "class_limit": None,
                "students_per_class_limit": None,
            }
    return profile


@router.get("/profile")
def get_profile(
    user_id: Optional[str] = None,
    auth: AuthPayload = Depends(require_student_viewer("user_id")),
):
    profile = _fetch_user_profile(user_id or auth.sub)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


class UpdateTutorialRequest(BaseModel):
    completed_tutorial: bool = False


@router.post("/update-tutorial")
def update_tutorial(body: UpdateTutorialRequest, auth: AuthPayload = Depends(get_auth)):
    user_service.update_tutorial_status(auth.sub, body.completed_tutorial)
    return {"message": "Tutorial status updated successfully"}


@router.get("/tutorial-status")
def get_tutorial_status(auth: AuthPayload = Depends(get_auth)):
    status = user_service.get_tutorial_status(auth.sub)
    return {"completed_tutorial": status}


