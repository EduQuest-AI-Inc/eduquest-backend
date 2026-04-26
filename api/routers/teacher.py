import logging
from typing import List

from canvasapi import Canvas
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from services.period.period_management_service import PeriodManagementService
from services.period.period_schedule_service import PeriodScheduleService

logger = logging.getLogger(__name__)

router = APIRouter()
period_management_service = PeriodManagementService()
period_schedule_service = PeriodScheduleService()


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


# ---------------------------------------------------------------------------
# Period schedule
# ---------------------------------------------------------------------------

class GenerateScheduleRequest(BaseModel):
    period_id: str


@router.post("/period-schedule/generate")
def generate_period_schedule(
    body: GenerateScheduleRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.generate_and_save_schedule(
            period_id=body.period_id, user_id=auth.sub
        )
        return {"message": "Schedule generated successfully", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error generating period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate schedule")


@router.get("/period-schedule")
def get_period_schedule(
    period_id: str = Query(...),
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.get_schedule(
            period_id=period_id, user_id=auth.sub
        )
        if result is None:
            raise HTTPException(
                status_code=404, detail="No schedule found for this period"
            )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error getting period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get schedule")


class UpdateScheduleRequest(BaseModel):
    period_id: str
    schedule: dict


@router.put("/period-schedule")
def update_period_schedule(
    body: UpdateScheduleRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.update_schedule(
            period_id=body.period_id,
            user_id=auth.sub,
            schedule_dict=body.schedule,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error updating period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update schedule")


class SetQuestWeeksRequest(BaseModel):
    period_id: str
    quest_enabled_weeks: List[int]


@router.put("/period-schedule/quest-weeks")
def set_period_quest_weeks(
    body: SetQuestWeeksRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.set_quest_weeks(
            period_id=body.period_id,
            user_id=auth.sub,
            quest_enabled_weeks=body.quest_enabled_weeks,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error setting quest weeks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set quest weeks")
