import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, require_roles
from data_access.period_dao import PeriodDAO
from services.curriculum.curriculum_service import CurriculumService
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

_curriculum_service = CurriculumService()
_period_dao = PeriodDAO()


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
    period = _period_dao.get_period_by_id(period_id)
    if not period:
        logger.warning("period not found: period_id=%s", period_id)
        raise HTTPException(status_code=404, detail=f"Period '{period_id}' not found")
    if period["owner_id"] != user_id:
        logger.warning(
            "ownership check failed: period_id=%s owner_id=%s caller_id=%s",
            period_id, period["owner_id"], user_id,
        )
        raise HTTPException(status_code=403, detail="Unauthorized")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/{period_id}/generate", status_code=202)
def trigger_generation(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        _curriculum_service.trigger_generation(period_id, background_tasks)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("trigger_generation error for period %s: %s", period_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"message": "Curriculum generation started"}


@router.get("/{period_id}")
def get_curriculum(
    period_id: str,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        return _curriculum_service.get_curriculum(period_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("get_curriculum error for period %s: %s", period_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{period_id}")
def save_curriculum(
    period_id: str,
    payload: _SavePayload,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        _curriculum_service.save_curriculum(period_id, payload.model_dump())
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("save_curriculum error for period %s: %s", period_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"message": "Curriculum saved"}


@router.patch("/{period_id}/concepts/{concept_name}")
def update_concept(
    period_id: str,
    concept_name: str,
    payload: _ConceptEditPayload,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    _assert_period_owner(period_id, auth.sub)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        _curriculum_service.update_concept(period_id, concept_name, fields)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("update_concept error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"message": "Concept updated"}


@router.patch("/{period_id}/skills/{skill_name}")
def update_skill(
    period_id: str,
    skill_name: str,
    payload: _SkillEditPayload,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    _assert_period_owner(period_id, auth.sub)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        _curriculum_service.update_skill(period_id, skill_name, fields)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("update_skill error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"message": "Skill updated"}


@router.post("/{period_id}/approve")
def approve_period(
    period_id: str,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT)),
):
    _assert_period_owner(period_id, auth.sub)
    try:
        _curriculum_service.approve_period(period_id)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("approve_period error for period %s: %s", period_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"message": "Period approved"}
