import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_bot_provider, require_active_membership
from bots.protocol import BotProviderProtocol
from services.curriculum.curriculum_service import CurriculumService
from services.enrollment.enrollment_service import EnrollmentService
from services.period.period_management_service import PeriodManagementService
from services.slides.pptx_generation_service import PptxGenerationService
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

_period_management_svc = PeriodManagementService()
_enrollment_service = EnrollmentService()


def _get_curriculum_service(
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
) -> CurriculumService:
    return CurriculumService(bot_provider=bot_provider)


def _get_slides_service(
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
) -> PptxGenerationService:
    return PptxGenerationService(bot_provider=bot_provider)


# ── Request models ─────────────────────────────────────────────────────────────

class _WeekPayload(BaseModel):
    week_number: int
    week_start: Optional[str] = None
    week_end: Optional[str] = None


class _LessonPayload(BaseModel):
    lesson_name: str
    week_number: int


class _ConceptPayload(BaseModel):
    concept_name: str
    lesson_name: str
    description: Optional[str] = None
    prerequisites: list[Any] = []
    key_takeaways: list[Any] = []
    common_misconceptions: list[Any] = []
    metadata: Optional[dict] = None


class _SkillPayload(BaseModel):
    skill_name: str
    description: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None
    mastery_threshold: float = 0.8
    mastery_criteria: Optional[list] = None
    metadata: Optional[dict] = None


class _ConceptSkillPayload(BaseModel):
    concept_name: str
    skill_name: str


class _SavePayload(BaseModel):
    weeks: list[_WeekPayload] = []
    lessons: list[_LessonPayload] = []
    concepts: list[_ConceptPayload] = []
    skills: list[_SkillPayload] = []
    concept_skills: list[_ConceptSkillPayload] = []


class _ConceptEditPayload(BaseModel):
    description: Optional[str] = None
    prerequisites: Optional[list[Any]] = None
    key_takeaways: Optional[list[Any]] = None
    common_misconceptions: Optional[list[Any]] = None
    metadata: Optional[dict] = None


class _SkillEditPayload(BaseModel):
    description: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None
    mastery_threshold: Optional[float] = None
    mastery_criteria: Optional[list] = None
    metadata: Optional[dict] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _assert_period_owner(period_id: str, user_id: str) -> None:
    period = _period_management_svc.get_period_by_id(period_id)
    if not period:
        logger.warning("period not found: period_id=%s", period_id)
        raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")
    if period["owner_id"] != user_id:
        logger.warning(
            "ownership check failed: period_id=%s owner_id=%s caller_id=%s",
            period_id, period["owner_id"], user_id,
        )
        raise HTTPException(status_code=403, detail="Unauthorized")


def _assert_student_enrolled(period_id: str, user_id: str) -> None:
    try:
        _enrollment_service.check_enrolled(user_id, period_id)
    except ValidationError:
        raise HTTPException(status_code=403, detail="Unauthorized")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/{period_id}/generate", status_code=202)
def trigger_generation(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(require_active_membership),
    svc: CurriculumService = Depends(_get_curriculum_service),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        svc.trigger_generation(period_id, background_tasks)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Curriculum generation started"}


@router.get("/{period_id}")
def get_curriculum(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
    svc: CurriculumService = Depends(_get_curriculum_service),
):
    if auth.role == Role.STUDENT:
        _assert_student_enrolled(period_id, auth.sub)
    else:
        _assert_period_owner(period_id, auth.sub)
    try:
        return svc.get_curriculum(period_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{period_id}")
def save_curriculum(
    period_id: str,
    payload: _SavePayload,
    auth: AuthPayload = Depends(require_active_membership),
    svc: CurriculumService = Depends(_get_curriculum_service),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        svc.save_curriculum(period_id, payload.model_dump())
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "Curriculum saved"}


@router.patch("/{period_id}/concepts/{concept_name}")
def update_concept(
    period_id: str,
    concept_name: str,
    payload: _ConceptEditPayload,
    auth: AuthPayload = Depends(require_active_membership),
    svc: CurriculumService = Depends(_get_curriculum_service),
):
    _assert_period_owner(period_id, auth.sub)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        svc.update_concept(period_id, concept_name, fields)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Concept updated"}


@router.patch("/{period_id}/skills/{skill_name}")
def update_skill(
    period_id: str,
    skill_name: str,
    payload: _SkillEditPayload,
    auth: AuthPayload = Depends(require_active_membership),
    svc: CurriculumService = Depends(_get_curriculum_service),
):
    _assert_period_owner(period_id, auth.sub)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        svc.update_skill(period_id, skill_name, fields)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Skill updated"}


@router.post("/{period_id}/approve", status_code=202)
def approve_period(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(require_active_membership),
    svc: CurriculumService = Depends(_get_curriculum_service),
    slides_svc: PptxGenerationService = Depends(_get_slides_service),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        lessons = svc.approve_period(period_id)
        slides_svc.start_batch(period_id, background_tasks, lessons)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"total_lessons": len(lessons)}
