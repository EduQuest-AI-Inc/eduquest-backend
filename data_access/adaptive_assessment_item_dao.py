from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.adaptive_assessment_item import AdaptiveAssessmentItem


class AdaptiveAssessmentItemDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("adaptive_assessment_item", jwt=jwt)

    def insert(self, item: AdaptiveAssessmentItem) -> dict[str, Any]:
        return self._insert(item.to_item())

    def get_by_id(self, item_id: str) -> dict[str, Any] | None:
        return self._select_by_id("item_id", item_id)

    def get_for_session(self, session_id: str) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
        )
        return response.data or []

    def update_answer(
        self,
        item_id: str,
        learner_answer: str,
        scored_result: str,
        misconception_id: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {
            "learner_answer": learner_answer,
            "scored_result": scored_result,
        }
        if misconception_id:
            updates["misconception_id"] = misconception_id
        self._update({"item_id": item_id}, updates)

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
