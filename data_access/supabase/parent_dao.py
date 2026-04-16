from typing import Dict, Any, List, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class ParentDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('parent')

    def add_parent(self, parent) -> None:
        self._insert({
            'parent_id': parent.parent_id,
            'first_name': parent.first_name,
            'last_name': parent.last_name,
            'email': parent.email,
            'email_lc': parent.email_lc,
            'password': parent.password,
            'linked_student_ids': getattr(parent, 'linked_student_ids', []),
        })

    def get_parent_by_id(self, parent_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('parent_id', parent_id)

    def get_parent_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('email_lc', email_lc)

    def update_parent(self, parent_id: str, updates: Dict[str, Any]) -> None:
        self._update({'parent_id': parent_id}, updates)

    def delete_parent(self, parent_id: str) -> None:
        self._delete({'parent_id': parent_id})
