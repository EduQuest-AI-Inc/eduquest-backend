from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.concept_skill import ConceptSkill


class ConceptSkillDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('concept_skill')

    def insert_concept_skill(self, cs: ConceptSkill) -> None:
        self._insert(cs.to_item())

    def get_skills_for_concept(self, period_id: str, concept_name: str) -> list[dict[str, Any]]:
        response = self._execute(
            self._table().select('*').eq('period_id', period_id).eq('concept_name', concept_name)
        )
        return response.data if response.data else []

    def get_concepts_for_skill(self, period_id: str, skill_name: str) -> list[dict[str, Any]]:
        response = self._execute(
            self._table().select('*').eq('period_id', period_id).eq('skill_name', skill_name)
        )
        return response.data if response.data else []
