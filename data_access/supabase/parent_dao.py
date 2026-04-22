from typing import Dict, Any, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO
from data_access.supabase.user_dao import UserDAO

SHARED_USER_FIELDS = {
    "first_name", "last_name", "email", "email_lc",
    "password", "last_login", "canvas_api_url", "canvas_api_key",
}


class ParentDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('parent')
        self._user_dao = UserDAO()

    def add_parent(self, parent) -> None:
        """Insert into user table first, then parent. Compensating delete on role insert failure."""
        self._user_dao._insert({
            'user_id': parent.user_id,
            'first_name': parent.first_name,
            'last_name': parent.last_name,
            'email': parent.email,
            'email_lc': parent.email_lc,
            'password': parent.password,
            'role': 'parent',
        })
        try:
            self._insert({
                'user_id': parent.user_id,
                'linked_user_ids': getattr(parent, 'linked_user_ids', []),
            })
        except Exception:
            self._user_dao.delete(parent.user_id)
            raise

    def get_parent_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._join_user('user_id', user_id)

    def get_parent_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        user = self._user_dao.get_by_email_lc(email_lc)
        if not user:
            return None
        return self.get_parent_by_id(user['user_id'])

    def update_parent(self, user_id: str, updates: Dict[str, Any]) -> None:
        user_updates = {k: v for k, v in updates.items() if k in SHARED_USER_FIELDS}
        parent_updates = {k: v for k, v in updates.items() if k not in SHARED_USER_FIELDS}
        if user_updates:
            self._user_dao.update(user_id, user_updates)
        if parent_updates:
            self._update({'user_id': user_id}, parent_updates)

    def delete_parent(self, user_id: str) -> None:
        self._user_dao.delete(user_id)

    def _join_user(self, id_column: str, id_value: str) -> Optional[Dict[str, Any]]:
        """JOIN parent + user and return a flat dict."""
        response = (
            self.client.table('parent')
            .select('*, user!inner(*)')
            .eq(id_column, id_value)
            .maybe_single()
            .execute()
        )
        data = self._row(response)
        if not data:
            return None
        data = dict(data)
        user_data = data.pop('user', {})
        data.update(user_data)
        return data
