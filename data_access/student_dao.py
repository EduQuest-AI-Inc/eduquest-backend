from typing import Dict, Any, Optional

from data_access.base_dao import SupabaseBaseDAO
from data_access.user_dao import UserDAO, SHARED_USER_FIELDS
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError


class StudentDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('student')
        self._user_dao = UserDAO()

    def add_student(self, student) -> None:
        """Insert into user table first, then student. Compensating delete on role insert failure."""
        self._user_dao._insert({
            'user_id': student.user_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.email,
            'password': student.password,
            'phone_number': getattr(student, 'phone_number', None),
            'role': 'student',
        })
        try:
            self._insert({
                'user_id': student.user_id,
                'grade': student.grade,
                'strength': getattr(student, 'strength', None),
                'weakness': getattr(student, 'weakness', None),
                'interest': getattr(student, 'interest', None),
                'learning_style': getattr(student, 'learning_style', None),
                'completed_tutorial': getattr(student, 'completed_tutorial', False),
                'school_name': getattr(student, 'school_name', None),
            })
        except Exception:
            self._user_dao.delete(student.user_id)
            raise

    def get_student_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._join_user('user_id', user_id)

    def get_student_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        user = self._user_dao.get_by_email(email)
        if not user:
            return None
        return self.get_student_by_id(user['user_id'])

    def update_student(self, user_id: str, updates: Dict[str, Any]) -> None:
        user_updates = {k: v for k, v in updates.items() if k in SHARED_USER_FIELDS}
        student_updates = {k: v for k, v in updates.items() if k not in SHARED_USER_FIELDS}
        if user_updates:
            self._user_dao.update(user_id, user_updates)
        if student_updates:
            self._update({'user_id': user_id}, student_updates)

    def delete_student(self, user_id: str) -> None:
        self._user_dao.delete(user_id)

    def update_tutorial_status(self, user_id: str, completed_tutorial: bool) -> None:
        if not user_id:
            raise ValidationError('User ID cannot be empty')
        if not isinstance(completed_tutorial, bool):
            raise ValidationError('completed_tutorial must be a boolean value')
        existing = self.get_student_by_id(user_id)
        if not existing:
            raise NotFoundError(f'Student with ID {user_id} not found')
        self._execute(self._table().update({'completed_tutorial': completed_tutorial}).eq('user_id', user_id))

    def get_tutorial_status(self, user_id: str) -> bool:
        if not user_id:
            return False
        student = self.get_student_by_id(user_id)
        if not student:
            return False
        return student.get('completed_tutorial', False)

    def needs_tutorial(self, user_id: str) -> bool:
        return not self.get_tutorial_status(user_id)

