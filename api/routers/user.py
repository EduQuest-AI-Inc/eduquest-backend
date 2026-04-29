import logging
from typing import Optional

from canvasapi import Canvas
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
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
    if role == "student":
        profile.pop("canvas_api_key", None)
    if role == "teacher":
        profile.setdefault("pilot_approved", False)
    return profile


def _check_student_viewer_access(auth: AuthPayload, user_id: str) -> None:
    if auth.role == "parent":
        linked = parent_dao.get_linked_student_ids(auth.sub)
        if user_id not in linked:
            raise HTTPException(status_code=403, detail="Access denied")
    elif auth.role == "teacher":
        if not period_service_u.has_teacher_access_to_student(auth.sub, user_id):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/profile")
def get_profile(
    user_id: Optional[str] = None,
    auth: AuthPayload = Depends(get_auth),
):
    if user_id:
        _check_student_viewer_access(auth, user_id)
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


class CanvasConnectRequest(BaseModel):
    api_url: str
    api_key: str


@router.post("/canvas/connect")
def canvas_connect(body: CanvasConnectRequest, auth: AuthPayload = Depends(get_auth)):
    try:
        canvas = Canvas(body.api_url, body.api_key)
        canvas.get_current_user()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Canvas credentials. Check your URL and token.")
    student_dao.update_canvas_credentials(auth.sub, body.api_url, body.api_key)
    return {"message": "Canvas connected"}


@router.get("/canvas/courses")
def canvas_courses(auth: AuthPayload = Depends(get_auth)):
    student = student_dao.get_student_by_id(auth.sub)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    api_url = student.get("canvas_api_url")
    api_key = student.get("canvas_api_key")
    if not api_url or not api_key:
        raise HTTPException(status_code=400, detail="Canvas not connected")
    try:
        canvas = Canvas(api_url, api_key)
        current_user = canvas.get_current_user()
        courses = [
            {"id": c.id, "name": getattr(c, "name", f"Course {c.id}")}
            for c in current_user.get_courses(enrollment_type="student")
        ]
        return {"courses": courses}
    except Exception as e:
        logger.error("Error fetching Canvas courses: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to fetch Canvas courses")


@router.delete("/canvas/disconnect")
def canvas_disconnect(auth: AuthPayload = Depends(get_auth)):
    student_dao.clear_canvas_credentials(auth.sub)
    return {"message": "Canvas disconnected"}
