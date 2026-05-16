import concurrent.futures
import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_auth, get_bot_provider, get_period
from bots.protocol import BotProviderProtocol
from services.curriculum.curriculum_service import CurriculumService
from services.enrollment.enrollment_service import EnrollmentService
from services.period.period_summer_quest_service import run_summer_quest_background_task as _run_summer_quest_generation
from services.slides.pptx_generation_service import PptxGenerationService
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

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

def _run_slides_and_quests_parallel(
    slides_svc: PptxGenerationService,
    period_id: str,
    owner_id: str,
    bot_provider: BotProviderProtocol,
) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(slides_svc.run_batch, period_id),
            executor.submit(
                _run_summer_quest_generation,
                period_id=period_id,
                owner_id=owner_id,
                bot_provider=bot_provider,
            ),
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.error("Parallel generation task failed: %s", exc, exc_info=True)


def _assert_period_owner(period: dict, user_id: str) -> None:
    if period["owner_id"] != user_id:
        logger.warning(
            "ownership check failed: period_id=%s owner_id=%s caller_id=%s",
            period.get("period_id"), period["owner_id"], user_id,
        )
        raise HTTPException(status_code=403, detail="Unauthorized")


def _assert_student_enrolled(period_id: str, user_id: str) -> None:
    try:
        _enrollment_service.check_enrolled(user_id, period_id)
    except ValidationError:
        raise HTTPException(status_code=403, detail="Unauthorized")


def _membership_or_summer(
    period_id: str,
    auth: AuthPayload = Depends(get_auth),
    period: dict = Depends(get_period),
) -> AuthPayload:
    """Bypass the membership gate for summer side quests; enforce it for all others."""
    if period.get("is_summer_quest"):
        return auth
    if auth.role not in (Role.TEACHER, Role.PARENT):
        raise HTTPException(
            status_code=403,
            detail={"error": "Forbidden", "code": "OWNER_ROLE_REQUIRED"},
        )
    from services.billing.membership_service import MembershipService
    access = MembershipService().evaluate_access(auth.sub, auth.role.value)
    if not access.has_active_membership:
        raise HTTPException(
            status_code=403,
            detail={"error": "Active membership required", "code": "MEMBERSHIP_REQUIRED"},
        )
    return auth


# ── Helpers ───────────────────────────────────────────────────────────────────


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/{period_id}/generate", status_code=202)
def trigger_generation(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(_membership_or_summer),
    svc: CurriculumService = Depends(_get_curriculum_service),
    period: dict = Depends(get_period),
):
    _assert_period_owner(period, auth.sub)
    try:
        svc.trigger_generation(period_id, background_tasks)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Curriculum generation started"}


@router.get("/{period_id}/status")
def get_curriculum_status(
    period_id: str,
    auth: AuthPayload = Depends(_membership_or_summer),
    period: dict = Depends(get_period),
):
    if auth.role == Role.STUDENT:
        if period.get("is_summer_quest") and period.get("owner_id") == auth.sub:
            pass
        else:
            _assert_student_enrolled(period_id, auth.sub)
    else:
        _assert_period_owner(period, auth.sub)
    return {"period_status": period["status"]}


@router.get("/{period_id}")
def get_curriculum(
    period_id: str,
    auth: AuthPayload = Depends(_membership_or_summer),
    svc: CurriculumService = Depends(_get_curriculum_service),
    period: dict = Depends(get_period),
):
    if auth.role == Role.STUDENT:
        if period.get("is_summer_quest") and period.get("owner_id") == auth.sub:
            pass  # student owns this summer quest — allow through
        else:
            _assert_student_enrolled(period_id, auth.sub)
    else:
        _assert_period_owner(period, auth.sub)
    try:
        return svc.get_curriculum(period_id, period=period)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{period_id}")
def save_curriculum(
    period_id: str,
    payload: _SavePayload,
    auth: AuthPayload = Depends(_membership_or_summer),
    svc: CurriculumService = Depends(_get_curriculum_service),
    period: dict = Depends(get_period),
):
    _assert_period_owner(period, auth.sub)
    try:
        svc.save_curriculum(period_id, payload.model_dump(), period=period)
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
    auth: AuthPayload = Depends(_membership_or_summer),
    svc: CurriculumService = Depends(_get_curriculum_service),
    period: dict = Depends(get_period),
):
    _assert_period_owner(period, auth.sub)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        svc.update_concept(period_id, concept_name, fields, period=period)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Concept updated"}


@router.patch("/{period_id}/skills/{skill_name}")
def update_skill(
    period_id: str,
    skill_name: str,
    payload: _SkillEditPayload,
    auth: AuthPayload = Depends(_membership_or_summer),
    svc: CurriculumService = Depends(_get_curriculum_service),
    period: dict = Depends(get_period),
):
    _assert_period_owner(period, auth.sub)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        svc.update_skill(period_id, skill_name, fields, period=period)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Skill updated"}


@router.post("/{period_id}/approve", status_code=202)
def approve_period(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(_membership_or_summer),
    svc: CurriculumService = Depends(_get_curriculum_service),
    slides_svc: PptxGenerationService = Depends(_get_slides_service),
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
    period: dict = Depends(get_period),
):
    _assert_period_owner(period, auth.sub)
    try:
        lessons = svc.approve_period(period_id, period=period)
        if period.get("is_summer_quest"):
            slides_svc.prepare_batch(period_id, lessons)
            background_tasks.add_task(
                _run_slides_and_quests_parallel,
                slides_svc=slides_svc,
                period_id=period_id,
                owner_id=auth.sub,
                bot_provider=bot_provider,
            )
        else:
            slides_svc.start_batch(period_id, background_tasks, lessons)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"total_lessons": len(lessons)}
