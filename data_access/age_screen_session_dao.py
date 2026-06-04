from typing import Any
from datetime import datetime, timezone

from data_access.base_dao import SupabaseBaseDAO


class AgeScreenSessionDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__("age_screen_session")

    def create(self, record: dict[str, Any]) -> None:
        self._insert(record)

    def consume(self, token_hash: str) -> dict[str, Any] | None:
        result = self._rpc("consume_age_screen_session", {"p_token_hash": token_hash})
        if not isinstance(result, list) or not result:
            return None
        return result[0]

    def get_valid(self, token_hash: str) -> dict[str, Any] | None:
        response = self._execute(
            self._table()
            .select("*")
            .eq("token_hash", token_hash)
            .is_("consumed_at", "null")
            .gt("expires_at", datetime.now(timezone.utc).isoformat())
            .maybe_single()
        )
        return self._row(response)
