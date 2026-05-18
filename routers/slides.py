import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from bots.protocol import BotProviderProtocol
from routers.deps import AuthPayload, Role, get_auth, get_bot_provider, get_period, require_roles
from exceptions.validation_error import ValidationError
from services.enrollment.enrollment_service import EnrollmentService
from services.lessons.lessons_service import LessonsService
from services.parent.parent_service import ParentService
from services.slides.pptx_generation_service import PptxGenerationService

logger = logging.getLogger(__name__)
router = APIRouter()

_lessons_svc = LessonsService()
_enrollment_svc = EnrollmentService()
_parent_svc = ParentService()


def _get_slides_service(
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
) -> PptxGenerationService:
    return PptxGenerationService(bot_provider=bot_provider)


@router.get("/{period_id}/pptx/status")
def get_pptx_status(
    period_id: str,
    auth: AuthPayload = Depends(get_auth),
    period: dict = Depends(get_period),
):
    is_owner = period["owner_id"] == auth.sub
    if not is_owner:
        # Student: must be enrolled in the period
        if auth.role == Role.STUDENT:
            enrollments = _enrollment_svc.get_enrollments_by_student(auth.sub)
            if not any(e["period_id"] == period_id for e in enrollments):
                raise HTTPException(status_code=403, detail="Unauthorized")
        # Parent: must have a linked child enrolled in the period
        elif auth.role == Role.PARENT:
            child_ids = _parent_svc.get_linked_student_ids(auth.sub)
            enrolled_period_ids = {
                e["period_id"]
                for child_id in child_ids
                for e in _enrollment_svc.get_enrollments_by_student(child_id)
            }
            if period_id not in enrolled_period_ids:
                raise HTTPException(status_code=403, detail="Unauthorized")
        else:
            raise HTTPException(status_code=403, detail="Unauthorized")

    pptx_rows = _lessons_svc.get_pptx_by_period(period_id)
    lessons = {les["lesson_id"]: les for les in _lessons_svc.get_lessons_by_period(period_id)}

    return [
        {
            "pptx_id": row["pptx_id"],
            "lesson_id": row["lesson_id"],
            "lesson_name": lessons.get(row["lesson_id"], {}).get("lesson_name"),
            "week_number": lessons.get(row["lesson_id"], {}).get("week_number"),
            "pptx_status": row["status"],
            "attempt_count": row.get("attempt_count", 0),
        }
        for row in pptx_rows
    ]


@router.post("/{period_id}/pptx/restart", status_code=202)
def restart_pptx_generation(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
    slides_svc: PptxGenerationService = Depends(_get_slides_service),
    period: dict = Depends(get_period),
):
    if period["owner_id"] != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        count = slides_svc.restart_batch(period_id, background_tasks)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"queued": count}
