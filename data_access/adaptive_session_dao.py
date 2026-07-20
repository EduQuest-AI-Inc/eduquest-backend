from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.adaptive.adaptive_session import AdaptiveSession


class AdaptiveSessionDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__("adaptive_session", jwt=jwt)

    def insert(self, session: AdaptiveSession) -> dict[str, Any]:
        return self._insert(session.to_item())

    def get_by_id(self, session_id: str) -> dict[str, Any] | None:
        return self._select_by_id("session_id", session_id)

    def update_status(
        self,
        session_id: str,
        status: str,
        completed_at: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {"status": status}
        if completed_at:
            updates["completed_at"] = completed_at
        self._update({"session_id": session_id}, updates)

    def get_for_learner_period(
        self, learner_id: str, period_id: str
    ) -> list[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select("*")
            .eq("learner_id", learner_id)
            .eq("period_id", period_id)
            .order("started_at", desc=True)
        )
        return response.data or []
