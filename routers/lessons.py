import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from bots.protocol import BotProviderProtocol
from routers.deps import AuthPayload, Role, get_auth, get_bot_provider, require_roles
from integrations import s3_service
from services.enrollment.enrollment_service import EnrollmentService
from services.lessons.lessons_service import LessonsService
from services.period.period_management_service import PeriodManagementService
from services.slides.pptx_generation_service import PptxGenerationService
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

_lessons_service = LessonsService()
_period_management_svc = PeriodManagementService()
_enrollment_service = EnrollmentService()


def _get_slides_service(
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
) -> PptxGenerationService:
    return PptxGenerationService(bot_provider=bot_provider)


def _assert_lesson_access(period_id: str, auth: AuthPayload) -> None:
    if auth.role == Role.STUDENT:
        try:
            _enrollment_service.check_enrolled(auth.sub, period_id)
        except ValidationError:
            raise HTTPException(status_code=403, detail="Unauthorized")
    else:
        period = _period_management_svc.get_period_by_id(period_id)
        if not period:
            raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")
        if period["owner_id"] != auth.sub:
            raise HTTPException(status_code=403, detail="Unauthorized")


@router.get("/{lesson_id}/pptx")
def get_lesson_pptx(
    lesson_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    pptx_row = _lessons_service.get_latest_done_pptx(lesson_id)
    if not pptx_row:
        raise HTTPException(status_code=404, detail="No completed PowerPoint for this lesson")

    _assert_lesson_access(pptx_row["period_id"], auth)

    lesson = _lessons_service.get_lesson_by_id(lesson_id)
    url = s3_service.generate_presigned_url(pptx_row["s3_key"], expiry=900)
    return {
        "url": url,
        "expires_in": 900,
        "version": 1,
        "lesson_name": lesson.get("lesson_name") if lesson else None,
    }


@router.post("/{lesson_id}/pptx/regenerate", status_code=202)
def regenerate_lesson_pptx(
    lesson_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
    slides_svc: PptxGenerationService = Depends(_get_slides_service),
):
    pptx_row = (
        _lessons_service.get_pptx_by_lesson_id(lesson_id)
        or _lessons_service.get_latest_done_pptx(lesson_id)
    )
    if not pptx_row:
        raise HTTPException(status_code=404, detail="No PowerPoint record for this lesson")
    _assert_lesson_access(pptx_row["period_id"], auth)
    try:
        return slides_svc.regenerate_lesson(lesson_id, background_tasks)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{lesson_id}/html")
def get_lesson_html(
    lesson_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    pptx_row = _lessons_service.get_latest_done_pptx(lesson_id)
    if not pptx_row:
        raise HTTPException(status_code=404, detail="No completed presentation for this lesson")
    if not pptx_row.get("html_key"):
        raise HTTPException(status_code=404, detail="HTML version not available for this lesson")

    _assert_lesson_access(pptx_row["period_id"], auth)

    url = s3_service.generate_presigned_url(pptx_row["html_key"], expiry=3600)
    return {"url": url, "expires_in": 3600}
