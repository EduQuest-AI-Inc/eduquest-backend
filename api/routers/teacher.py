import logging

from canvasapi import Canvas
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from services.period.period_management_service import PeriodManagementService

logger = logging.getLogger(__name__)

router = APIRouter()
period_management_service = PeriodManagementService()


# ---------------------------------------------------------------------------
# Get teacher periods
# ---------------------------------------------------------------------------

@router.get("/periods")
def get_teacher_periods(auth: AuthPayload = Depends(get_auth)):
    try:
        result = period_management_service.get_periods_by_owner(auth.sub)
        return {"periods": result}
    except Exception as e:
        logger.error("Error in get_teacher_periods: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Canvas courses
# ---------------------------------------------------------------------------

class CanvasCoursesRequest(BaseModel):
    api_url: str
    api_key: str


@router.post("/canvas/courses")
def list_canvas_courses(
    body: CanvasCoursesRequest,
    auth: AuthPayload = Depends(get_auth),
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
        return {"courses": courses}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to Canvas: {e}")
