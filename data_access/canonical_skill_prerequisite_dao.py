from typing import Any

from data_access.base_dao import SupabaseBaseDAO


class CanonicalSkillPrerequisiteDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("canonical_skill_prerequisite", jwt=jwt)

    def insert(self, skill_id: str, prerequisite_id: str) -> None:
        self._insert({"skill_id": skill_id, "prerequisite_id": prerequisite_id})

    def get_prerequisites(self, skill_id: str) -> list[dict[str, Any]]:
        return self._select_eq("skill_id", skill_id)

    def delete_for_skill(self, skill_id: str) -> None:
        self._delete({"skill_id": skill_id})
