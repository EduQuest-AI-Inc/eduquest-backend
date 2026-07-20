from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.learning_event import LearningEvent


class LearningEventDAO(SupabaseBaseDAO):
    """Append-only event log. Never update or delete rows."""

    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("learning_event", jwt=jwt)

    def insert(self, event: LearningEvent) -> dict[str, Any]:
        return self._insert(event.to_item())

    def get_for_learner_skill(
        self, learner_id: str, canonical_skill_id: str
    ) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select("*")
            .eq("learner_id", learner_id)
            .eq("canonical_skill_id", canonical_skill_id)
            .order("created_at", desc=True)
        )
        return response.data or []

    def get_latest_for_learner_skill(
        self, learner_id: str, canonical_skill_id: str
    ) -> dict[str, Any] | None:
        response = self._execute(
            self._table()
            .select("*")
            .eq("learner_id", learner_id)
            .eq("canonical_skill_id", canonical_skill_id)
            .order("created_at", desc=True)
            .limit(1)
            .maybe_single()
        )
        return response.data if response else None

    def get_for_learner(
        self, learner_id: str, event_type: str | None = None
    ) -> list[dict[str, Any]]:
        query = self._table().select("*").eq("learner_id", learner_id)
        if event_type:
            query = query.eq("event_type", event_type)
        response = self._execute(query.order("created_at", desc=True))
        return response.data or []
