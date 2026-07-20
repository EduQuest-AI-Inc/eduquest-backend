from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.learner_skill_state import LearnerSkillState


class LearnerSkillStateDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("learner_skill_state", jwt=jwt)

    def upsert(self, state: LearnerSkillState) -> dict[str, Any]:
        return self._upsert(state.to_item())

    def get_one(self, learner_id: str, canonical_skill_id: str) -> dict[str, Any] | None:
        response = self._execute(
            self._table()
            .select("*")
            .eq("learner_id", learner_id)
            .eq("canonical_skill_id", canonical_skill_id)
            .maybe_single()
        )
        return response.data if response else None

    def get_for_learner(self, learner_id: str) -> list[dict[str, Any]]:
        return self._select_eq("learner_id", learner_id)

    def get_for_learner_by_skill_ids(
        self, learner_id: str, canonical_skill_ids: list[str]
    ) -> list[dict[str, Any]]:
        if not canonical_skill_ids:
            return []
        response = self._execute(
            self._table()
            .select("*")
            .eq("learner_id", learner_id)
            .in_("canonical_skill_id", canonical_skill_ids)
        )
        return response.data or []
