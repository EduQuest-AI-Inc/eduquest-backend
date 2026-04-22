from typing import Dict, Any, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO
from data_access.supabase.user_dao import UserDAO

SHARED_USER_FIELDS = {
    "first_name", "last_name", "email", "email_lc",
    "password", "last_login", "canvas_api_url", "canvas_api_key",
}


class TeacherDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('teacher')
        self._user_dao = UserDAO()

    def add_teacher(self, teacher) -> None:
        """Insert into user table first, then teacher. Compensating delete on role insert failure."""
        self._user_dao._insert({
            'user_id': teacher.user_id,
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'email': teacher.email,
            'email_lc': teacher.email_lc,
            'password': teacher.password,
            'role': 'teacher',
        })
        try:
            self._insert({
                'user_id': teacher.user_id,
                'pilot_approved': getattr(teacher, 'pilot_approved', False),
                'school_id': getattr(teacher, 'school_id', None),
            })
        except Exception:
            self._user_dao.delete(teacher.user_id)
            raise

    def get_teacher_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._join_user('user_id', user_id)

    def update_teacher(self, user_id: str, updates: Dict[str, Any]) -> None:
        user_updates = {k: v for k, v in updates.items() if k in SHARED_USER_FIELDS}
        teacher_updates = {k: v for k, v in updates.items() if k not in SHARED_USER_FIELDS}
        if user_updates:
            self._user_dao.update(user_id, user_updates)
        if teacher_updates:
            self._update({'user_id': user_id}, teacher_updates)

    def delete_teacher(self, user_id: str) -> None:
        self._user_dao.delete(user_id)

    def _join_user(self, id_column: str, id_value: str) -> Optional[Dict[str, Any]]:
        """JOIN teacher + user and return a flat dict."""
        response = (
            self.client.table('teacher')
            .select('*, user!inner(*)')
            .eq(id_column, id_value)
            .maybe_single()
            .execute()
        )
        if not response or not response.data:
            return None
        data = dict(response.data)
        user_data = data.pop('user', {})
        data.update(user_data)
        return data
