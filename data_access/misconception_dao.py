from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.misconception import Misconception


class MisconceptionDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("misconception", jwt=jwt)

    def insert(self, misconception: Misconception) -> dict[str, Any]:
        return self._insert(misconception.to_item())

    def get_for_skill(self, canonical_skill_id: str) -> list[dict[str, Any]]:
        return self._select_eq("canonical_skill_id", canonical_skill_id)

    def delete_for_skill(self, canonical_skill_id: str) -> None:
        self._delete({"canonical_skill_id": canonical_skill_id})

    def get_by_id(self, misconception_id: str) -> dict[str, Any] | None:
        return self._select_by_id("misconception_id", misconception_id)
