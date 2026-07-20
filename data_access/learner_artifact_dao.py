from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.learner_artifact import LearnerArtifact


class LearnerArtifactDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("learner_artifact", jwt=jwt)

    def insert(self, artifact: LearnerArtifact) -> dict[str, Any]:
        return self._insert(artifact.to_item())

    def get_for_learner_period(
        self, learner_id: str, period_id: str
    ) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select("*")
            .eq("learner_id", learner_id)
            .eq("period_id", period_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
        )
        return response.data or []

    def mark_deleted(self, artifact_id: str, deleted_at: str) -> None:
        self._update({"artifact_id": artifact_id}, {"deleted_at": deleted_at})

    def get_by_id(self, artifact_id: str) -> dict[str, Any] | None:
        return self._select_by_id("artifact_id", artifact_id)
