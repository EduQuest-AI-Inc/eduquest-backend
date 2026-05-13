import logging

from fastapi import APIRouter, Depends, HTTPException

from routers.deps import AuthPayload, Role, get_auth
from data_access.lesson_pptx_dao import LessonPptxDAO
from data_access.lesson_dao import LessonDAO
from data_access.period_dao import PeriodDAO
from data_access.enrollment_dao import EnrollmentDAO
from data_access.parent_dao import ParentDAO

logger = logging.getLogger(__name__)
router = APIRouter()

_lesson_pptx_dao = LessonPptxDAO()
_lesson_dao = LessonDAO()
_period_dao = PeriodDAO()
_enrollment_dao = EnrollmentDAO()
_parent_dao = ParentDAO()


@router.get("/{period_id}/pptx/status")
def get_pptx_status(
    period_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")

    is_owner = period["owner_id"] == auth.sub
    if not is_owner:
        # Student: must be enrolled in the period
        if auth.role == Role.STUDENT:
            enrollments = _enrollment_dao.get_enrollments_by_student(auth.sub)
            if not any(e["period_id"] == period_id for e in enrollments):
                raise HTTPException(status_code=403, detail="Unauthorized")
        # Parent: must have a linked child enrolled in the period
        elif auth.role == Role.PARENT:
            child_ids = _parent_dao.get_linked_student_ids(auth.sub)
            enrolled_period_ids = {
                e["period_id"]
                for child_id in child_ids
                for e in _enrollment_dao.get_enrollments_by_student(child_id)
            }
            if period_id not in enrolled_period_ids:
                raise HTTPException(status_code=403, detail="Unauthorized")
        else:
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
