from typing import Dict, Any, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class StudentDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('student')

    def add_student(self, student) -> None:
        self._insert({
            'user_id': student.user_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.email,
            'email_lc': student.email_lc,
            'password': student.password,
            'grade': getattr(student, 'grade', None),
            'strength': getattr(student, 'strength', None),
            'weakness': getattr(student, 'weakness', None),
            'interest': getattr(student, 'interest', None),
            'learning_style': getattr(student, 'learning_style', None),
            'completed_tutorial': getattr(student, 'completed_tutorial', False),
            'school_id': getattr(student, 'school_id', None),
        })

    def get_student_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('user_id', user_id)

    def get_student_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('email_lc', email_lc)

    def update_student(self, user_id: str, updates: Dict[str, Any]) -> None:
        updates['last_login'] = datetime.now(timezone.utc).isoformat()
        self._update({'user_id': user_id}, updates)

    def delete_student(self, user_id: str) -> None:
        self._delete({'user_id': user_id})

    def update_long_term_goal(self, user_id: str, period_id: str, goal: str) -> None:
        """Upsert long-term goal into the student_long_term_goal table."""
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
        self._update({'user_id': user_id}, {'canvas_api_url': api_url, 'canvas_api_key': api_key})

    def clear_canvas_credentials(self, user_id: str) -> None:
        self._update({'user_id': user_id}, {'canvas_api_url': None, 'canvas_api_key': None})
