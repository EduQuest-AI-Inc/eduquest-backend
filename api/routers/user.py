import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth, require_student_viewer
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
    try:
        user_service.update_tutorial_status(auth.sub, body.completed_tutorial)
        return {"message": "Tutorial status updated successfully"}
    except Exception as e:
        logger.error("Error updating tutorial status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update tutorial status")


@router.get("/tutorial-status")
def get_tutorial_status(auth: AuthPayload = Depends(get_auth)):
    try:
        status = user_service.get_tutorial_status(auth.sub)
        return {"completed_tutorial": status}
    except Exception as e:
        logger.error("Error getting tutorial status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get tutorial status")


