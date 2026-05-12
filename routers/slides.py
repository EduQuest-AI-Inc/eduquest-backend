import logging

from fastapi import APIRouter, Depends, HTTPException

from routers.deps import AuthPayload, require_active_membership
from data_access.lesson_pptx_dao import LessonPptxDAO
from data_access.lesson_dao import LessonDAO
from data_access.period_dao import PeriodDAO

logger = logging.getLogger(__name__)
router = APIRouter()

_lesson_pptx_dao = LessonPptxDAO()
_lesson_dao = LessonDAO()
_period_dao = PeriodDAO()


@router.get("/{period_id}/pptx/status")
def get_pptx_status(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")
    if period["owner_id"] != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")

    pptx_rows = _lesson_pptx_dao.get_by_period(period_id)
    lessons = {les["lesson_id"]: les for les in _lesson_dao.get_lessons_by_period(period_id)}

    return [
        {
            "pptx_id": row["pptx_id"],
            "lesson_id": row["lesson_id"],
            "lesson_name": lessons.get(row["lesson_id"], {}).get("lesson_name"),
            "week_number": lessons.get(row["lesson_id"], {}).get("week_number"),
            "pptx_status": row["status"],
        }
        for row in pptx_rows
    ]
