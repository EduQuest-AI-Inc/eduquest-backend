"""Adaptive pretest service — drives item selection, generation, scoring, and state updates."""
import logging
from datetime import datetime, timezone
from typing import Any

from bots.protocol import BotProviderProtocol
from data_access.adaptive_assessment_item_dao import AdaptiveAssessmentItemDAO
from data_access.adaptive_session_dao import AdaptiveSessionDAO
from data_access.canonical_skill_dao import CanonicalSkillDAO
from data_access.learner_skill_state_dao import LearnerSkillStateDAO
from data_access.skill_dao import SkillDAO
from exceptions.not_found_error import NotFoundError
from exceptions.permission_error import PermissionError
from models.adaptive.adaptive_assessment_item import AdaptiveAssessmentItem
from models.adaptive.adaptive_session import AdaptiveSession
from models.adaptive.learning_event import LearningEvent
from services.adaptive.learning_event_service import LearningEventService
from services.adaptive.skill_classifier import SkillClassifier

logger = logging.getLogger(__name__)

MAX_ITEMS = 20


class PretestService:
    KNOWN_MASTERY = 0.85
    KNOWN_CONF = 0.65
    GAP_MASTERY = 0.60

    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        session_dao=None,
        item_dao=None,
        skill_dao=None,
        state_dao=None,
        canonical_dao=None,
        event_service=None,
    ) -> None:
        self._bot_provider = bot_provider
        self._session_dao = session_dao or AdaptiveSessionDAO()
        self._item_dao = item_dao or AdaptiveAssessmentItemDAO()
        self._skill_dao = skill_dao or SkillDAO()
        self._state_dao = state_dao or LearnerSkillStateDAO()
        self._canonical_dao = canonical_dao or CanonicalSkillDAO()
        self._event_service = event_service or LearningEventService()
        self._classifier = SkillClassifier()

    async def start_pretest(self, *, learner_id: str, period_id: str) -> dict[str, Any]:
        """Create a pretest session and return the first item.

        Returns {session_id, item_id, prompt, skill_name, complete}.
        """
        session_row = self._session_dao.insert(AdaptiveSession(
            learner_id=learner_id,
            period_id=period_id,
            session_type="pretest",
            status="active",
            started_at=datetime.now(timezone.utc).isoformat(),
        ))
        session_id = session_row["session_id"]

        next_skill = self._select_next_skill(
            learner_id=learner_id,
            period_id=period_id,
            answered_skill_ids=set(),
        )
        if next_skill is None:
            self._session_dao.update_status(
                session_id, "completed",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            return {"session_id": session_id, "complete": True, "item_id": None, "prompt": None}

        item = await self._generate_and_save_item(
            session_id=session_id,
            learner_id=learner_id,
            skill=next_skill,
        )
        return {
            "session_id": session_id,
            "item_id": item["item_id"],
            "prompt": item["prompt"],
            "skill_name": next_skill["name"],
            "complete": False,
        }

    async def answer_item(
        self,
        *,
        session_id: str,
        item_id: str,
        answer: str,
        learner_id: str,
    ) -> dict[str, Any]:
        """Score an answer, write learning event, and return next item or completion.

        Returns {scored_result, rationale, complete, next_item_id?, next_prompt?}.
        """
        session = self._session_dao.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id!r} not found")
        if session["learner_id"] != learner_id:
            raise PermissionError("Not your session")
        if session["status"] != "active":
            return {"complete": True, "scored_result": None, "rationale": "Session already complete"}

        item = self._item_dao.get_by_id(item_id)
        if not item or item["session_id"] != session_id:
            raise NotFoundError(f"Item {item_id!r} not found in session {session_id!r}")

        canonical_skill_id = item.get("canonical_skill_id")
        skill_name = item.get("skill_name_cache") or self._resolve_skill_name(
            canonical_skill_id, session["period_id"]
        )

        agent = self._bot_provider.create_pretest_agent()
        scoring = await agent.score_answer(
            skill_name=skill_name or "",
            item_prompt=item["prompt"],
            learner_answer=answer,
        )

        self._item_dao.update_answer(item_id, answer, scoring.result)

        if canonical_skill_id:
            self._event_service.write_event(
                LearningEvent(
                    learner_id=learner_id,
                    canonical_skill_id=canonical_skill_id,
                    event_type="pretest",
                    result=scoring.result,
                ),
                period_id=session["period_id"],
                skill_name=skill_name,
            )

        answered_skill_ids = {
            it["canonical_skill_id"]
            for it in self._item_dao.get_for_session(session_id)
            if it.get("canonical_skill_id") and it.get("scored_result")
        }

        if len(answered_skill_ids) >= MAX_ITEMS:
            self._complete_session(session_id)
            return {
                "scored_result": scoring.result,
                "rationale": scoring.rationale,
                "complete": True,
            }

        next_skill = self._select_next_skill(
            learner_id=learner_id,
            period_id=session["period_id"],
            answered_skill_ids=answered_skill_ids,
        )
        if next_skill is None:
            self._complete_session(session_id)
            return {
                "scored_result": scoring.result,
                "rationale": scoring.rationale,
                "complete": True,
            }

        next_item = await self._generate_and_save_item(
            session_id=session_id,
            learner_id=learner_id,
            skill=next_skill,
        )
        return {
            "scored_result": scoring.result,
            "rationale": scoring.rationale,
            "complete": False,
            "next_item_id": next_item["item_id"],
            "next_prompt": next_item["prompt"],
            "next_skill_name": next_skill["name"],
        }

    # ── private helpers ───────────────────────────────────────────────────────

    def _select_next_skill(
        self,
        learner_id: str,
        period_id: str,
        answered_skill_ids: set[str],
    ) -> dict | None:
        """Return canonical skill dict for the next skill to probe, or None if done."""
        period_skills = self._skill_dao.get_skills_by_period(period_id)
        canonical_ids = [
            s["canonical_skill_id"]
            for s in period_skills
            if s.get("canonical_skill_id")
        ]
        if not canonical_ids:
            return None

        states_by_id = {
            row["canonical_skill_id"]: row
            for row in self._state_dao.get_for_learner_by_skill_ids(learner_id, canonical_ids)
        }

        for cid in canonical_ids:
            if cid in answered_skill_ids:
                continue
            state = states_by_id.get(cid)
            if self._classifier.classify(state) == "known":
                continue
            skill = self._canonical_dao.get_by_id(cid)
            if skill:
                return skill
        return None

    async def _generate_and_save_item(
        self,
        session_id: str,
        learner_id: str,
        skill: dict,
    ) -> dict:
        """Generate an assessment item and save it to adaptive_assessment_item."""
        agent = self._bot_provider.create_pretest_agent()
        generated = await agent.generate_item(
            skill_name=skill["name"],
            description=skill.get("description") or "",
        )
        item_row = self._item_dao.insert(AdaptiveAssessmentItem(
            session_id=session_id,
            learner_id=learner_id,
            canonical_skill_id=skill["canonical_skill_id"],
            prompt=generated.prompt,
        ))
        return item_row

    def _complete_session(self, session_id: str) -> None:
        self._session_dao.update_status(
            session_id, "completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _resolve_skill_name(
        self, canonical_skill_id: str | None, period_id: str
    ) -> str | None:
        """Find skill_name for a canonical_skill_id within a specific period."""
        if not canonical_skill_id:
            return None
        period_skills = self._skill_dao.get_skills_by_period(period_id)
        for s in period_skills:
            if s.get("canonical_skill_id") == canonical_skill_id:
                return s["skill_name"]
        return None
