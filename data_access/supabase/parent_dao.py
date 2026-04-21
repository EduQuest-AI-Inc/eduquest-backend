from typing import Dict, Any, List, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class ParentDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('parent')

    def add_parent(self, parent) -> None:
        self._insert({
            'user_id': parent.user_id,
            'first_name': parent.first_name,
            'last_name': parent.last_name,
            'email': parent.email,
            'email_lc': parent.email_lc,
            'password': parent.password,
            'linked_user_ids': getattr(parent, 'linked_user_ids', []),
        })

    def get_parent_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('user_id', user_id)

    def get_parent_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('email_lc', email_lc)

    def update_parent(self, user_id: str, updates: Dict[str, Any]) -> None:
        self._update({'user_id': user_id}, updates)

    def delete_parent(self, user_id: str) -> None:
        self._delete({'user_id': user_id})
