from typing import Dict, Any, Optional

from data_access.base_dao import SupabaseBaseDAO
from data_access.user_dao import UserDAO, SHARED_USER_FIELDS


class TeacherDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('teacher', jwt=jwt)
        self._user_dao = UserDAO(jwt=jwt)

    def add_teacher(self, teacher) -> None:
        """Insert into user table first, then teacher. Compensating delete on role insert failure."""
        self._user_dao._insert({
            'user_id': teacher.user_id,
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'email': teacher.email,
            'password': teacher.password,
            'phone_number': getattr(teacher, 'phone_number', None),
            'role': 'teacher',
        })
        try:
            self._insert({
                'user_id': teacher.user_id,
                'pilot_approved': getattr(teacher, 'pilot_approved', False),
                'school_name': getattr(teacher, 'school_name', None),
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

    def update_canvas_credentials(self, user_id: str, api_url: str, api_key: str) -> None:
        self._update({'user_id': user_id}, {'canvas_api_url': api_url, 'canvas_api_key': api_key})

    def clear_canvas_credentials(self, user_id: str) -> None:
        self._update({'user_id': user_id}, {'canvas_api_url': None, 'canvas_api_key': None})

    def delete_teacher(self, user_id: str) -> None:
        self._user_dao.delete(user_id)
