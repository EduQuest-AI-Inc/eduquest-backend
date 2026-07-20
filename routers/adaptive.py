"""
Adaptive Knowledge Engine router.

All endpoints require Role.STUDENT authentication.
Phase 2 adds: GET /knowledge-graph
Phase 3 adds: POST /courses
Phase 4 adds: POST /courses/{period_id}/seed
Phase 5 adds: POST /courses/{period_id}/pretest/start, POST /sessions/{session_id}/answer
Phase 6 adds: GET /courses/{period_id}/plan
Phase 7 adds: POST /courses/{period_id}/learn/start, POST /loops/{loop_id}/attempt
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from routers.deps import AuthPayload, Role, get_bot_provider, require_roles

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Phase 2 — canonical knowledge graph view
# ---------------------------------------------------------------------------

@router.get("/knowledge-graph")
def get_knowledge_graph(
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
) -> dict[str, Any]:
    """
    Returns the student's current canonical knowledge state:
    all canonical skills they have evidence for, with mastery/confidence.
    """
    from data_access.canonical_skill_dao import CanonicalSkillDAO
    from data_access.learner_skill_state_dao import LearnerSkillStateDAO

    state_dao = LearnerSkillStateDAO()  # admin client — cross-period read
    skill_dao = CanonicalSkillDAO()

    states = state_dao.get_for_learner(auth.sub)
    nodes = []
    for state in states:
        skill = skill_dao.get_by_id(state["canonical_skill_id"])
        nodes.append({
            "canonical_skill_id": state["canonical_skill_id"],
            "name": skill["name"] if skill else "Unknown",
            "domain": skill.get("domain") if skill else None,
            "mastery": state["mastery"],
            "confidence": state["confidence"],
            "evidence_count": state["evidence_count"],
            "last_verified_at": state.get("last_verified_at"),
        })

    return {"nodes": nodes}


# ---------------------------------------------------------------------------
# Phase 3 — self-directed course creation (wired in Phase 3)
# ---------------------------------------------------------------------------

@router.post("/courses")
def create_course(
    body: dict[str, Any],
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    bot_provider=Depends(get_bot_provider),
) -> dict[str, Any]:
    from services.adaptive.adaptive_course_service import AdaptiveCourseService
    svc = AdaptiveCourseService(bot_provider=bot_provider)
    period_id = svc.create_course(
        student_id=auth.sub,
        name=body["name"],
        description=body.get("description", ""),
        background_tasks=background_tasks,
    )
    return {"period_id": period_id}


# ---------------------------------------------------------------------------
# Phase 4 — artifact seeding (wired in Phase 4)
# ---------------------------------------------------------------------------

@router.post("/courses/{period_id}/seed")
async def seed_artifacts(
    period_id: str,
    body: dict[str, Any],
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    bot_provider=Depends(get_bot_provider),
) -> dict[str, Any]:
    from services.adaptive.artifact_seed_service import ArtifactSeedService
    svc = ArtifactSeedService(bot_provider=bot_provider)
    result = await svc.seed(
        learner_id=auth.sub,
        period_id=period_id,
        artifact_type=body.get("artifact_type", "free_text"),
        text_content=body.get("text_content", ""),
    )
    return result


# ---------------------------------------------------------------------------
# Phase 5 — adaptive pretest (wired in Phase 5)
# ---------------------------------------------------------------------------

@router.post("/courses/{period_id}/pretest/start")
async def start_pretest(
    period_id: str,
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    bot_provider=Depends(get_bot_provider),
) -> dict[str, Any]:
    from services.adaptive.pretest_service import PretestService
    svc = PretestService(bot_provider=bot_provider)
    return await svc.start_pretest(learner_id=auth.sub, period_id=period_id)


@router.post("/sessions/{session_id}/answer")
async def answer_pretest_item(
    session_id: str,
    body: dict[str, Any],
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    bot_provider=Depends(get_bot_provider),
) -> dict[str, Any]:
    from services.adaptive.pretest_service import PretestService
    svc = PretestService(bot_provider=bot_provider)
    return await svc.answer_item(
        session_id=session_id,
        item_id=body["item_id"],
        answer=body["answer"],
        learner_id=auth.sub,
    )


# ---------------------------------------------------------------------------
# Phase 6 — skill plan (wired in Phase 6)
# ---------------------------------------------------------------------------

@router.get("/courses/{period_id}/plan")
def get_course_plan(
    period_id: str,
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
) -> dict[str, Any]:
    from services.adaptive.skill_classifier import SkillClassifier
    from data_access.skill_dao import SkillDAO
    from data_access.learner_skill_state_dao import LearnerSkillStateDAO

    skill_dao = SkillDAO()
    state_dao = LearnerSkillStateDAO()
    classifier = SkillClassifier()

    skills = skill_dao.get_skills_by_period(period_id)
    skill_ids = [s["canonical_skill_id"] for s in skills if s.get("canonical_skill_id")]
    states_by_id = {
        row["canonical_skill_id"]: row
        for row in state_dao.get_for_learner_by_skill_ids(auth.sub, skill_ids)
    }

    known, gap, uncertain = [], [], []
    for s in skills:
        cid = s.get("canonical_skill_id")
        if not cid:
            continue
        state = states_by_id.get(cid)
        classification = classifier.classify(state)
        entry = {"skill_name": s["skill_name"], "canonical_skill_id": cid}
        if classification == "known":
            entry["skip_reason"] = f"Mastered (score {state['mastery']:.0%})"
            known.append(entry)
        elif classification == "gap":
            gap.append(entry)
        else:
            entry["will_verify"] = True
            uncertain.append(entry)

    return {"known": known, "gap": gap, "uncertain": uncertain}


# ---------------------------------------------------------------------------
# Phase 7 — teaching loop (wired in Phase 7)
# ---------------------------------------------------------------------------

@router.post("/courses/{period_id}/learn/start")
async def start_learning(
    period_id: str,
    body: dict[str, Any],
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    bot_provider=Depends(get_bot_provider),
) -> dict[str, Any]:
    from services.adaptive.teaching_loop_service import TeachingLoopService
    svc = TeachingLoopService(bot_provider=bot_provider)
    return await svc.start_loop(learner_id=auth.sub, period_id=period_id)


@router.post("/loops/{loop_id}/attempt")
async def submit_attempt(
    loop_id: str,
    body: dict[str, Any],
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    bot_provider=Depends(get_bot_provider),
) -> dict[str, Any]:
    from services.adaptive.teaching_loop_service import TeachingLoopService
    svc = TeachingLoopService(bot_provider=bot_provider)
    return await svc.submit_attempt(
        session_id=loop_id,
        answer=body.get("answer", ""),
        learner_id=auth.sub,
    )
