import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth
from services.period.period_schedule_service import PeriodScheduleService

logger = logging.getLogger(__name__)
router = APIRouter()
period_schedule_service = PeriodScheduleService()


# ─── Request models ───────────────────────────────────────────────────────────

class GenerateScheduleRequest(BaseModel):
    period_id: str
    course_description: Optional[str] = None


class SaveAllScheduleRequest(BaseModel):
    period_id: str
    schedule: dict
    quest_enabled_weeks: List[int]


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/period-schedule")
def generate_period_schedule(
    body: GenerateScheduleRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.generate_and_save_schedule(
            period_id=body.period_id,
            user_id=auth.sub,
            course_description=body.course_description,
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
            raise HTTPException(status_code=404, detail="No schedule found for this period")
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


@router.put("/period-schedule")
def save_period_schedule_and_quest_weeks(
    body: SaveAllScheduleRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.save_schedule_and_quest_weeks(
            period_id=body.period_id,
            user_id=auth.sub,
            schedule_dict=body.schedule,
            quest_enabled_weeks=body.quest_enabled_weeks,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error saving period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save schedule")
