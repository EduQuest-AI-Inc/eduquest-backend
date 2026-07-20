from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.canonical_skill import CanonicalSkill


class CanonicalSkillDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("canonical_skill", jwt=jwt)

    def insert(self, skill: CanonicalSkill) -> dict[str, Any]:
        return self._insert(skill.to_item())

    def get_by_id(self, canonical_skill_id: str) -> dict[str, Any] | None:
        return self._select_by_id("canonical_skill_id", canonical_skill_id)

    def find_by_normalized_name(self, normalized_name: str) -> dict[str, Any] | None:
        rows = self._execute(
            self._table()
            .select("*")
            .eq("normalized_name", normalized_name)
            .limit(1)
        ).data
        return rows[0] if rows else None

    def find_by_embedding_similarity(
        self, embedding: list[float], threshold: float, match_count: int = 5
    ) -> list[dict[str, Any]]:
        result = self._rpc(
            "match_canonical_skills",
            {
                "query_embedding": embedding,
                "threshold": threshold,
                "match_count": match_count,
            },
        )
        return result if isinstance(result, list) else []

    def get_by_ids(self, canonical_skill_ids: list[str]) -> list[dict[str, Any]]:
        if not canonical_skill_ids:
            return []
        response = self._execute(
            self._table().select("*").in_("canonical_skill_id", canonical_skill_ids)
        )
        return response.data or []

    def update_embedding(self, canonical_skill_id: str, embedding: list[float]) -> None:
        self._update({"canonical_skill_id": canonical_skill_id}, {"embedding": embedding})
