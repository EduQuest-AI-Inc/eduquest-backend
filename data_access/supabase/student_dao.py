from typing import Dict, Any, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO
from data_access.supabase.user_dao import UserDAO

SHARED_USER_FIELDS = {
    "first_name", "last_name", "email", "email_lc",
    "password", "last_login", "canvas_api_url", "canvas_api_key",
}


class StudentDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('student')
        self._user_dao = UserDAO()

    def add_student(self, student) -> None:
        """Insert into user table first, then student. Compensating delete on role insert failure."""
        self._user_dao._insert({
            'user_id': student.user_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.email,
            'email_lc': student.email_lc,
            'password': student.password,
            'role': 'student',
            'canvas_api_url': getattr(student, 'canvas_api_url', None),
            'canvas_api_key': getattr(student, 'canvas_api_key', None),
        })
        try:
            self._insert({
                'user_id': student.user_id,
                'grade': getattr(student, 'grade', None),
                'strength': getattr(student, 'strength', None),
                'weakness': getattr(student, 'weakness', None),
                'interest': getattr(student, 'interest', None),
                'learning_style': getattr(student, 'learning_style', None),
                'completed_tutorial': getattr(student, 'completed_tutorial', False),
                'school_id': getattr(student, 'school_id', None),
            })
        except Exception:
            self._user_dao.delete(student.user_id)
            raise

    def get_student_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._join_user('user_id', user_id)

    def get_student_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        user = self._user_dao.get_by_email_lc(email_lc)
        if not user:
            return None
        return self.get_student_by_id(user['user_id'])

    def update_student(self, user_id: str, updates: Dict[str, Any]) -> None:
        user_updates = {k: v for k, v in updates.items() if k in SHARED_USER_FIELDS}
        student_updates = {k: v for k, v in updates.items() if k not in SHARED_USER_FIELDS}
        user_updates['last_login'] = datetime.now(timezone.utc).isoformat()
        self._user_dao.update(user_id, user_updates)
        if student_updates:
            self._update({'user_id': user_id}, student_updates)

    def delete_student(self, user_id: str) -> None:
        self._user_dao.delete(user_id)

    def update_long_term_goal(self, user_id: str, period_id: str, goal: str) -> None:
        self.client.table('student_long_term_goal').upsert({
            'user_id': user_id,
            'period_id': period_id,
            'goal_text': goal,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).execute()

    def update_tutorial_status(self, user_id: str, completed_tutorial: bool) -> None:
        if not user_id:
            raise ValueError('User ID cannot be empty')
        if not isinstance(completed_tutorial, bool):
            raise ValueError('completed_tutorial must be a boolean value')

        existing = self.get_student_by_id(user_id)
        if not existing:
            raise ValueError(f'Student with ID {user_id} not found')

        self._table().update({'completed_tutorial': completed_tutorial}).eq(
            'user_id', user_id
        ).execute()

    def get_tutorial_status(self, user_id: str) -> bool:
        if not user_id:
            return False
        student = self.get_student_by_id(user_id)
        if not student:
            return False
        return student.get('completed_tutorial', False)

    def needs_tutorial(self, user_id: str) -> bool:
        return not self.get_tutorial_status(user_id)

    def update_canvas_credentials(self, user_id: str, api_url: str, api_key: str) -> None:
        self._user_dao.update(user_id, {'canvas_api_url': api_url, 'canvas_api_key': api_key})

    def clear_canvas_credentials(self, user_id: str) -> None:
        self._user_dao.update(user_id, {'canvas_api_url': None, 'canvas_api_key': None})

    def _join_user(self, id_column: str, id_value: str) -> Optional[Dict[str, Any]]:
        """JOIN student + user and return a flat dict."""
        response = (
            self.client.table('student')
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
