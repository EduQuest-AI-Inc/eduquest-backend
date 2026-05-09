import logging

from canvasapi import Canvas
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, require_roles
from data_access.aggregated_metrics_dao import AggregatedMetricsDAO
from data_access.period_dao import PeriodDAO
from data_access.teacher_dao import TeacherDAO
from services.period.period_management_service import PeriodManagementService

logger = logging.getLogger(__name__)

router = APIRouter()
period_management_service = PeriodManagementService()
aggregated_metrics_dao = AggregatedMetricsDAO()
period_dao_t = PeriodDAO()
teacher_dao = TeacherDAO()


# ---------------------------------------------------------------------------
# Get teacher periods
# ---------------------------------------------------------------------------

@router.get("/periods")
def get_teacher_periods(auth: AuthPayload = Depends(require_roles(Role.TEACHER))):
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
            teacher_dao.update_canvas_credentials(auth.sub, body.api_url, body.api_key)
        except Exception as e:
            logger.warning("Failed to persist Canvas credentials for %s: %s", auth.sub, e)
        return {"courses": courses}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to Canvas: {e}")


# ---------------------------------------------------------------------------
# Skill mastery metrics
# ---------------------------------------------------------------------------

@router.get("/skill-mastery")
def get_skill_mastery(
    period_id: str = Query(...),
    auth: AuthPayload = Depends(require_roles(Role.TEACHER)),
):
    period = period_dao_t.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Forbidden")
    return aggregated_metrics_dao.get_by_period_id(period_id)
