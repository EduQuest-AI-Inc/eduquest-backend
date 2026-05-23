from typing import Dict, Any
from data_access.base_dao import SupabaseBaseDAO


class FeedbackDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('user_feedback', jwt=jwt)

    def insert(self, user_id: str, message: str) -> Dict[str, Any]:
        data = {"user_id": user_id, "message": message}
        self._insert(data)
        return data
