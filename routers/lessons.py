import logging

from fastapi import APIRouter, Depends, HTTPException

from routers.deps import AuthPayload, Role, get_auth
from data_access.lesson_dao import LessonDAO
from data_access.lesson_pptx_dao import LessonPptxDAO
from data_access.period_dao import PeriodDAO
from integrations import s3_service
from services.enrollment.enrollment_service import EnrollmentService
from exceptions.validation_error import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

_lesson_dao = LessonDAO()
_lesson_pptx_dao = LessonPptxDAO()
_period_dao = PeriodDAO()
_enrollment_service = EnrollmentService()


def _assert_lesson_access(period_id: str, auth: AuthPayload) -> None:
    if auth.role == Role.STUDENT:
        try:
            _enrollment_service.check_enrolled(auth.sub, period_id)
        except ValidationError:
            raise HTTPException(status_code=403, detail="Unauthorized")
    else:
        period = _period_dao.get_period_by_id(period_id)
        if not period:
            raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")
        if period["owner_id"] != auth.sub:
            raise HTTPException(status_code=403, detail="Unauthorized")


@router.get("/{lesson_id}/pptx")
def get_lesson_pptx(
    lesson_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    pptx_row = _lesson_pptx_dao.get_latest_done(lesson_id)
    if not pptx_row:
        raise HTTPException(status_code=404, detail="No completed PowerPoint for this lesson")

    _assert_lesson_access(pptx_row["period_id"], auth)

    lesson = _lesson_dao.get_by_lesson_id(lesson_id)
    url = s3_service.generate_presigned_url(pptx_row["s3_key"], expiry=900)
    return {
        "url": url,
        "expires_in": 900,
        "version": 1,
        "lesson_name": lesson.get("lesson_name") if lesson else None,
    }


@router.get("/{lesson_id}/html")
def get_lesson_html(
    lesson_id: str,
    auth: AuthPayload = Depends(get_auth),
):
    pptx_row = _lesson_pptx_dao.get_latest_done(lesson_id)
    if not pptx_row:
        raise HTTPException(status_code=404, detail="No completed presentation for this lesson")
    if not pptx_row.get("html_key"):
        raise HTTPException(status_code=404, detail="HTML version not available for this lesson")

    _assert_lesson_access(pptx_row["period_id"], auth)

    url = s3_service.generate_presigned_url(pptx_row["html_key"], expiry=3600)
    return {"url": url, "expires_in": 3600}
