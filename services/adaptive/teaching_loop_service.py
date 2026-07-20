"""Teaching loop service — orchestrates modality selection, teaching, scoring, and remediation."""
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from bots.protocol import BotProviderProtocol
from data_access.adaptive_assessment_item_dao import AdaptiveAssessmentItemDAO
from data_access.adaptive_session_dao import AdaptiveSessionDAO
from data_access.canonical_skill_dao import CanonicalSkillDAO
from data_access.learner_skill_state_dao import LearnerSkillStateDAO
from data_access.misconception_dao import MisconceptionDAO
from data_access.skill_dao import SkillDAO
from exceptions.not_found_error import NotFoundError
from exceptions.permission_error import PermissionError
from models.adaptive.adaptive_assessment_item import AdaptiveAssessmentItem
from models.adaptive.adaptive_session import AdaptiveSession
from models.adaptive.learning_event import LearningEvent
from services.adaptive.learning_event_service import LearningEventService
from services.adaptive.skill_classifier import SkillClassifier

logger = logging.getLogger(__name__)

_DEFAULT_MODALITY: Literal["worked_example", "analogy"] = "worked_example"


class TeachingLoopService:
    def __init__(
        self,
        *,
        bot_provider: BotProviderProtocol,
        session_dao=None,
        item_dao=None,
        skill_dao=None,
        state_dao=None,
        canonical_dao=None,
        misconception_dao=None,
        event_service=None,
    ) -> None:
        self._bot_provider = bot_provider
        self._session_dao = session_dao or AdaptiveSessionDAO()
        self._item_dao = item_dao or AdaptiveAssessmentItemDAO()
        self._skill_dao = skill_dao or SkillDAO()
        self._state_dao = state_dao or LearnerSkillStateDAO()
        self._canonical_dao = canonical_dao or CanonicalSkillDAO()
        self._misconception_dao = misconception_dao or MisconceptionDAO()
        self._event_service = event_service or LearningEventService()
        self._classifier = SkillClassifier()

    async def start_loop(self, *, learner_id: str, period_id: str) -> dict[str, Any]:
        """Select the next gap/uncertain skill, generate teaching content, open a session.

        Returns {session_id, skill_name, modality, content, retrieval_prompt, complete}.
        """
        skill = self._select_next_skill(learner_id, period_id, taught_skill_ids=set())
        if skill is None:
            return {"complete": True, "session_id": None}

        modality = self._select_modality(learner_id, skill["canonical_skill_id"])

        misconception_ctx = self._pick_misconception(skill["canonical_skill_id"])
        teaching_agent = self._bot_provider.create_teaching_agent()
        content = await teaching_agent.teach(
            skill_name=skill["name"],
            skill_description=skill.get("description") or "",
            modality=modality,
            misconception_signature=misconception_ctx.get("signature") if misconception_ctx else None,
            misconception_remediation=misconception_ctx.get("remediation_strategy") if misconception_ctx else None,
        )

        session_row = self._session_dao.insert(AdaptiveSession(
            learner_id=learner_id,
            period_id=period_id,
            session_type="teaching_loop",
            status="active",
            started_at=datetime.now(timezone.utc).isoformat(),
            metadata={"canonical_skill_id": skill["canonical_skill_id"]},
        ))
        session_id = session_row["session_id"]

        item_row = self._item_dao.insert(AdaptiveAssessmentItem(
            session_id=session_id,
            learner_id=learner_id,
            canonical_skill_id=skill["canonical_skill_id"],
            prompt=content.retrieval_prompt,
            modality=modality,
        ))

        return {
            "session_id": session_id,
            "skill_name": skill["name"],
            "modality": content.modality,
            "content": content.content,
            "retrieval_prompt": content.retrieval_prompt,
            "item_id": item_row["item_id"],
            "complete": False,
        }

    async def submit_attempt(
        self,
        *,
        session_id: str,
        answer: str,
        learner_id: str,
    ) -> dict[str, Any]:
        """Score a learner's attempt, diagnose errors, and return next content or completion.

        Returns {scored_result, complete, content?, retrieval_prompt?, modality?}.
        """
        session = self._session_dao.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id!r} not found")
        if session["learner_id"] != learner_id:
            raise PermissionError("Not your session")
        if session["status"] != "active":
            return {"complete": True, "scored_result": None}

        items = self._item_dao.get_for_session(session_id)
        pending = [it for it in items if not it.get("scored_result")]
        if not pending:
            self._complete_session(session_id)
            return {"complete": True, "scored_result": None}

        current_item = pending[-1]
        item_id = current_item["item_id"]
        canonical_skill_id = session.get("metadata", {}).get("canonical_skill_id") or current_item.get("canonical_skill_id")

        skill = self._canonical_dao.get_by_id(canonical_skill_id) if canonical_skill_id else None
        skill_name = skill["name"] if skill else ""
        period_id = session["period_id"]
        skill_name_in_period = self._resolve_skill_name(canonical_skill_id, period_id) if canonical_skill_id else None

        pretest_agent = self._bot_provider.create_pretest_agent()
        scoring = await pretest_agent.score_answer(
            skill_name=skill_name,
            item_prompt=current_item["prompt"],
            learner_answer=answer,
        )

        misconception_id = None
        if scoring.result == "incorrect" and canonical_skill_id:
            misconception_id = await self._diagnose_misconception(
                skill_name=skill_name,
                wrong_answer=answer,
                canonical_skill_id=canonical_skill_id,
            )

        self._item_dao.update_answer(item_id, answer, scoring.result, misconception_id)

        if canonical_skill_id:
            event = LearningEvent(
                learner_id=learner_id,
                canonical_skill_id=canonical_skill_id,
                event_type="loop_attempt",
                result=scoring.result,
                misconception_id=misconception_id,
            )
            self._event_service.write_event(
                event,
                period_id=period_id,
                skill_name=skill_name_in_period,
            )

        if scoring.result == "correct":
            self._complete_session(session_id)
            return {"scored_result": "correct", "complete": True}

        # Incorrect or partial — generate remediation content
        modality = self._select_modality(learner_id, canonical_skill_id)
        misconception_ctx = (
            self._misconception_dao.get_by_id(misconception_id)
            if misconception_id else None
        )
        teaching_agent = self._bot_provider.create_teaching_agent()
        content = await teaching_agent.teach(
            skill_name=skill_name,
            skill_description=skill.get("description") or "" if skill else "",
            modality=modality,
            misconception_signature=misconception_ctx.get("signature") if misconception_ctx else None,
            misconception_remediation=misconception_ctx.get("remediation_strategy") if misconception_ctx else None,
        )

        next_item_row = self._item_dao.insert(AdaptiveAssessmentItem(
            session_id=session_id,
            learner_id=learner_id,
            canonical_skill_id=canonical_skill_id,
            prompt=content.retrieval_prompt,
            modality=modality,
        ))

        return {
            "scored_result": scoring.result,
            "complete": False,
            "content": content.content,
            "modality": content.modality,
            "retrieval_prompt": content.retrieval_prompt,
            "next_item_id": next_item_row["item_id"],
        }

    # ── private helpers ───────────────────────────────────────────────────────

    def _select_next_skill(
        self,
        learner_id: str,
        period_id: str,
        taught_skill_ids: set[str],
    ) -> dict | None:
        """Return the next skill to teach: gaps first, then uncertain."""
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

        gaps, uncertain = [], []
        for cid in canonical_ids:
            if cid in taught_skill_ids:
                continue
            state = states_by_id.get(cid)
            cls = self._classifier.classify(state)
            if cls == "gap":
                gaps.append(cid)
            elif cls == "uncertain":
                uncertain.append(cid)

        priority = gaps + uncertain
        for cid in priority:
            skill = self._canonical_dao.get_by_id(cid)
            if skill:
                return skill
        return None

    def _select_modality(
        self,
        learner_id: str,
        canonical_skill_id: str | None,
    ) -> Literal["worked_example", "analogy"]:
        """Choose modality from history: prefer modality that last produced 'correct'."""
        if not canonical_skill_id:
            return _DEFAULT_MODALITY
        history = self._item_dao.get_for_learner_skill(learner_id, canonical_skill_id)
        for item in history:
            if item.get("scored_result") == "correct" and item.get("modality"):
                return item["modality"]
        return _DEFAULT_MODALITY

    def _pick_misconception(self, canonical_skill_id: str | None) -> dict | None:
        """Return a seeded misconception to address proactively, if any."""
        if not canonical_skill_id:
            return None
        misconceptions = self._misconception_dao.get_for_skill(canonical_skill_id)
        return misconceptions[0] if misconceptions else None

    async def _diagnose_misconception(
        self,
        skill_name: str,
        wrong_answer: str,
        canonical_skill_id: str,
    ) -> str | None:
        """Diagnose wrong answer and return misconception_id if matched, else None."""
        known = self._misconception_dao.get_for_skill(canonical_skill_id)
        agent = self._bot_provider.create_misconception_agent()
        try:
            result = await agent.diagnose(
                skill_name=skill_name,
                wrong_answer=wrong_answer,
                known_misconceptions=known,
            )
            return result.misconception_id
        except Exception:
            logger.warning(
                "misconception diagnosis failed for skill=%s (non-fatal)", skill_name
            )
            return None

    def _complete_session(self, session_id: str) -> None:
        self._session_dao.update_status(
            session_id, "completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _resolve_skill_name(
        self, canonical_skill_id: str, period_id: str
    ) -> str | None:
        period_skills = self._skill_dao.get_skills_by_period(period_id)
        for s in period_skills:
            if s.get("canonical_skill_id") == canonical_skill_id:
                return s["skill_name"]
        return None
