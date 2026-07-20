"""Learning event emission and learner_skill_state maintenance.

write_event() is the general path for pretest / loop_attempt / embedded_check events.
seed_from_artifact() handles artifact seeds with per-skill confidence caps.
Both are synchronous — no AI calls, just DB writes.
"""
import logging
from datetime import datetime, timezone

from data_access.learner_skill_state_dao import LearnerSkillStateDAO
from data_access.learning_event_dao import LearningEventDAO
from data_access.student_skill_mastery_dao import StudentSkillMasteryDAO
from models.adaptive.learner_skill_state import LearnerSkillState
from models.adaptive.learning_event import LearningEvent

logger = logging.getLogger(__name__)

# Mastery deltas applied per result type for active assessment events
_MASTERY_STEP: dict[str, float] = {
    "correct":   +0.15,
    "partial":   +0.07,
    "incorrect": -0.05,
}

# Confidence set after each active assessment event (represents certainty in the reading)
_CONFIDENCE_SET: dict[str, float] = {
    "correct":   0.90,
    "partial":   0.65,
    "incorrect": 0.50,
}


class LearningEventService:
    HALF_LIFE_DAYS = 45

    def __init__(
        self,
        *,
        event_dao=None,
        state_dao=None,
        mastery_dao=None,
    ) -> None:
        self._event_dao = event_dao or LearningEventDAO()
        self._state_dao = state_dao or LearnerSkillStateDAO()
        self._mastery_dao = mastery_dao or StudentSkillMasteryDAO()

    def write_event(
        self,
        event: LearningEvent,
        *,
        period_id: str | None = None,
        skill_name: str | None = None,
    ) -> None:
        """Append event, update learner_skill_state, optionally sync student_skill_mastery.

        Pass period_id + skill_name when the context is known (pretest, loop, grading hook)
        so the teacher dashboard projection stays current. Omit for cross-period events.
        """
        self._event_dao.insert(event)
        if event.canonical_skill_id and event.result != "seeded":
            self._update_state(event)
            if period_id and skill_name:
                self._sync_mastery_projection(event, period_id, skill_name)

    def seed_from_artifact(
        self,
        learner_id: str,
        period_id: str,  # noqa: ARG002 — reserved for future cross-period filtering
        skills: list[dict],
    ) -> None:
        """Seed learning state from artifact evidence without triggering mastery projection sync.

        skills: list of {canonical_skill_id: str, confidence_cap: float}
        confidence_cap: max confidence that can be set by this artifact type
          - transcript/verified: <= 0.65
          - free-text self-report: <= 0.35
        """
        for skill_item in skills:
            canonical_skill_id = skill_item.get("canonical_skill_id")
            if not canonical_skill_id:
                continue
            confidence_cap = float(skill_item.get("confidence_cap", 0.35))
            confidence_cap = min(confidence_cap, 0.65)  # hard ceiling — seeds never reach "known"

            event = LearningEvent(
                learner_id=learner_id,
                canonical_skill_id=canonical_skill_id,
                event_type="artifact_seed",
                result="seeded",
            )
            try:
                self._event_dao.insert(event)
                self._update_seeded_state(learner_id, canonical_skill_id, confidence_cap)
            except Exception:
                logger.warning(
                    "seed_from_artifact failed for learner=%s skill=%s (non-fatal)",
                    learner_id, canonical_skill_id,
                )

    @staticmethod
    def decayed_confidence(confidence: float, last_verified_at: str | None) -> float:
        """Apply 45-day half-life decay to confidence. Used at read time only."""
        if not last_verified_at or confidence == 0.0:
            return 0.0
        try:
            dt = datetime.fromisoformat(last_verified_at)
            days = (datetime.now(timezone.utc) - dt).days
        except (ValueError, TypeError):
            return 0.0
        return confidence * (0.5 ** (days / LearningEventService.HALF_LIFE_DAYS))

    # ── private helpers ───────────────────────────────────────────────────────

    def _update_state(self, event: LearningEvent) -> None:
        """Update learner_skill_state for a non-seeded event (pretest/loop/grading)."""
        state = self._state_dao.get_one(event.learner_id, event.canonical_skill_id)
        mastery = state["mastery"] if state else 0.0
        evidence_count = (state["evidence_count"] if state else 0) + 1

        step = _MASTERY_STEP.get(event.result, 0.0)
        new_mastery = min(max(mastery + step, 0.0), 1.0)
        new_confidence = _CONFIDENCE_SET.get(event.result, state["confidence"] if state else 0.0)

        self._state_dao.upsert(LearnerSkillState(
            learner_id=event.learner_id,
            canonical_skill_id=event.canonical_skill_id,
            mastery=new_mastery,
            confidence=new_confidence,
            last_verified_at=datetime.now(timezone.utc).isoformat(),
            evidence_count=evidence_count,
        ))

    def _update_seeded_state(
        self,
        learner_id: str,
        canonical_skill_id: str,
        confidence_cap: float,
    ) -> None:
        """Raise mastery/confidence to the artifact cap without ever lowering higher values."""
        state = self._state_dao.get_one(learner_id, canonical_skill_id)
        cur_mastery = state["mastery"] if state else 0.0
        cur_confidence = state["confidence"] if state else 0.0
        cur_count = (state["evidence_count"] if state else 0) + 1

        # Seeds raise to cap but never lower existing values from active assessment
        new_mastery = max(cur_mastery, confidence_cap)
        new_confidence = max(cur_confidence, confidence_cap)

        self._state_dao.upsert(LearnerSkillState(
            learner_id=learner_id,
            canonical_skill_id=canonical_skill_id,
            mastery=new_mastery,
            confidence=new_confidence,
            last_verified_at=datetime.now(timezone.utc).isoformat(),
            evidence_count=cur_count,
        ))

    def _sync_mastery_projection(
        self,
        event: LearningEvent,
        period_id: str,
        skill_name: str,
    ) -> None:
        """Write current mastery to student_skill_mastery so teacher dashboards stay current."""
        state = self._state_dao.get_one(event.learner_id, event.canonical_skill_id)
        if not state:
            return
        try:
            self._mastery_dao.upsert_score(
                student_id=event.learner_id,
                period_id=period_id,
                skill_name=skill_name,
                score=state["mastery"],
            )
        except Exception:
            logger.warning(
                "mastery projection sync failed for learner=%s period=%s skill=%s (non-fatal)",
                event.learner_id, period_id, skill_name,
            )
