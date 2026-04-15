from typing import Dict, Any, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class StudentDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('student')

    def add_student(self, student) -> None:
        self._insert({
            'student_id': student.student_id,
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

    def get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('student_id', student_id)

    def get_student_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('email_lc', email_lc)

    def update_student(self, student_id: str, updates: Dict[str, Any]) -> None:
        updates['last_login'] = datetime.now(timezone.utc).isoformat()
        self._update({'student_id': student_id}, updates)

    def delete_student(self, student_id: str) -> None:
        self._delete({'student_id': student_id})

    def update_long_term_goal(self, student_id: str, period_id: str, goal: str) -> None:
        """Upsert long-term goal into the student_long_term_goal table."""
        self.client.table('student_long_term_goal').upsert({
            'student_id': student_id,
            'period_id': period_id,
            'goal_text': goal,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).execute()

    def update_tutorial_status(self, student_id: str, completed_tutorial: bool) -> None:
        if not student_id:
            raise ValueError('Student ID cannot be empty')
        if not isinstance(completed_tutorial, bool):
            raise ValueError('completed_tutorial must be a boolean value')

        existing = self.get_student_by_id(student_id)
        if not existing:
            raise ValueError(f'Student with ID {student_id} not found')

        # Direct update without touching last_login
        self._table().update({'completed_tutorial': completed_tutorial}).eq(
            'student_id', student_id
        ).execute()

    def get_tutorial_status(self, student_id: str) -> bool:
        if not student_id:
            return False
        student = self.get_student_by_id(student_id)
        if not student:
            return False
        return student.get('completed_tutorial', False)

    def needs_tutorial(self, student_id: str) -> bool:
        return not self.get_tutorial_status(student_id)
