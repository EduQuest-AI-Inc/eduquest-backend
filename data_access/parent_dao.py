from typing import Dict, Any, Optional, List

from data_access.base_dao import SupabaseBaseDAO
from data_access.user_dao import UserDAO, SHARED_USER_FIELDS


class ParentDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('parent', jwt=jwt)
        self._user_dao = UserDAO(jwt=jwt)

    def add_parent(self, parent) -> None:
        """Insert into user table first, then parent. Compensating delete on role insert failure."""
        self._user_dao._insert({
            'user_id': parent.user_id,
            'first_name': parent.first_name,
            'last_name': parent.last_name,
            'email': parent.email,
            'password': parent.password,
            'phone_number': getattr(parent, 'phone_number', None),
            'role': 'parent',
        })
        try:
            self._insert({
                'user_id': parent.user_id,
                'linked_student_ids': getattr(parent, 'linked_student_ids', []),
            })
        except Exception:
            self._user_dao.delete(parent.user_id)
            raise

    def get_parent_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._join_user('user_id', user_id)

    def get_parent_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        user = self._user_dao.get_by_email(email)
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

    def get_linked_student_ids(self, user_id: str) -> List[str]:
        parent = self.get_parent_by_id(user_id)
        if not parent:
            return []
        return parent.get('linked_student_ids', [])

    def get_parents_by_student_id(self, student_id: str) -> List[Dict[str, Any]]:
        response = self._execute(
            self._table()
            .select('*')
            .contains('linked_student_ids', [student_id])
        )
        return self._rows(response.data)
