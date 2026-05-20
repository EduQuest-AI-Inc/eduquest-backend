from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.concept import Concept


class ConceptDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('concept', jwt=jwt)

    def insert_concept(self, concept: Concept) -> None:
        self._insert(concept.to_item())

    def get_concepts_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def get_concept(self, period_id: str, concept_name: str) -> dict[str, Any] | None:
        response = self._execute(
            self._table().select('*').eq('period_id', period_id).eq('concept_name', concept_name).maybe_single()
        )
        if response is None or response.data is None:
            return None
        return response.data

    def update_concept(self, period_id: str, concept_name: str, fields: dict[str, Any]) -> None:
        self._update({'period_id': period_id, 'concept_name': concept_name}, fields)

    def delete_all_for_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})
