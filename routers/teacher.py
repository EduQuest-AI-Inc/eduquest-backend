import logging

from canvasapi import Canvas
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from responses.teacher import CanvasCoursesResponse, SkillMasteryOut, TeacherPeriodsResponse

from routers.deps import AuthPayload, Role, require_roles
from services.period.period_management_service import PeriodManagementService
from services.tracking import Events, track_event
from services.user.teacher_service import TeacherService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/periods", response_model=TeacherPeriodsResponse)
def get_teacher_periods(auth: AuthPayload = Depends(require_roles(Role.TEACHER))):
    svc = PeriodManagementService(jwt=auth.token)
    result = svc.get_periods_by_owner(auth.sub)
    return {"periods": result}


class CanvasCoursesRequest(BaseModel):
    api_url: str
    api_key: str


@router.post("/canvas/courses", response_model=CanvasCoursesResponse)
def list_canvas_courses(
    body: CanvasCoursesRequest,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER)),
):
    try:
        canvas = Canvas(body.api_url, body.api_key)
        current_user = canvas.get_current_user()
        courses = []
        for course in current_user.get_courses(enrollment_type="teacher"):
            try:
                courses.append({
                    "id": course.id,
                    "name": getattr(course, "name", f"Course {course.id}"),
                })
            except Exception:
                continue
        try:
            teacher_service = TeacherService(jwt=auth.token)
            teacher_service.update_canvas_credentials(auth.sub, body.api_url, body.api_key)
        except Exception as exc:
            logger.warning("Failed to persist Canvas credentials for %s: %s", auth.sub, exc)
        return {"courses": courses}
    except HTTPException:
        raise
    except Exception as exc:
        track_event(
            user_id=auth.sub,
            event=Events.CANVAS_CONNECT_FAILED,
            properties={"failure_reason": "api_error", "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=400, detail=f"Failed to connect to Canvas: {exc}")


@router.get("/skill-mastery", response_model=list[SkillMasteryOut])
def get_skill_mastery(
    period_id: str = Query(...),
    auth: AuthPayload = Depends(require_roles(Role.TEACHER)),
):
    period_mgmt = PeriodManagementService(jwt=auth.token)
    period = period_mgmt.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Forbidden")
    teacher_service = TeacherService(jwt=auth.token)
    return teacher_service.get_aggregated_metrics(period_id)
