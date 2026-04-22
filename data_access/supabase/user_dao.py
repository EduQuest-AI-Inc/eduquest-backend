from typing import Dict, Any, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class UserDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('user')

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('user_id', user_id)

    def get_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('email_lc', email_lc)

    def update(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        result = self._update({'user_id': user_id}, updates)
        return result[0] if result else {}

    def delete(self, user_id: str) -> None:
        self._delete({'user_id': user_id})
