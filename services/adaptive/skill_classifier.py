"""Skill classifier — applies confidence decay and returns known / gap / uncertain."""
from datetime import datetime, timezone
from typing import Literal


class SkillClassifier:
    KNOWN_MASTERY = 0.85
    KNOWN_CONF = 0.65
    GAP_MASTERY = 0.60
    HALF_LIFE_DAYS = 45

    def classify(self, state: dict | None) -> Literal["known", "gap", "uncertain"]:
        """Classify a learner's relationship to a skill.

        state: a learner_skill_state row dict (or None for no evidence).
        Decay is applied at read time only — never written to DB.
        """
        if not state:
            return "uncertain"
        mastery = float(state.get("mastery", 0.0))
        confidence = float(state.get("confidence", 0.0))
        last_verified_at = state.get("last_verified_at")

        decayed = self._decay(confidence, last_verified_at)
        if mastery >= self.KNOWN_MASTERY and decayed >= self.KNOWN_CONF:
            return "known"
        if mastery < self.GAP_MASTERY:
            return "gap"
        return "uncertain"

    def _decay(self, confidence: float, last_verified_at: str | None) -> float:
        if not last_verified_at or confidence == 0.0:
            return 0.0
        try:
            dt = datetime.fromisoformat(last_verified_at)
            days = (datetime.now(timezone.utc) - dt).days
        except (ValueError, TypeError):
            return 0.0
        return confidence * (0.5 ** (days / self.HALF_LIFE_DAYS))
