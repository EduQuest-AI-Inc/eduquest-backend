from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.skill_resolution_decision import SkillResolutionDecision


class SkillResolutionDecisionDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("skill_resolution_decision", jwt=jwt)

    def insert(self, decision: SkillResolutionDecision) -> dict[str, Any]:
        return self._insert(decision.to_item())

    def get_for_skill(self, period_id: str, skill_name: str) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select("*")
            .eq("period_id", period_id)
            .eq("skill_name", skill_name)
            .order("created_at", desc=True)
        )
        return response.data or []
