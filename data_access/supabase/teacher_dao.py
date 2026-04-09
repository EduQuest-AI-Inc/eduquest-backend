from typing import Dict, Any, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class TeacherDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('teacher')

    def add_teacher(self, teacher) -> None:
        self._insert({
            'teacher_id': teacher.teacher_id,
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'email': teacher.email,
            'email_lc': teacher.email_lc,
            'password': teacher.password,
            'pilot_approved': getattr(teacher, 'pilot_approved', False),
            'school_id': getattr(teacher, 'school_id', None),
        })

    def get_teacher_by_id(self, teacher_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('teacher_id', teacher_id)

    def get_teacher_by_email_lc(self, email_lc: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('email_lc', email_lc)

    def update_teacher(self, teacher_id: str, updates: Dict[str, Any]) -> None:
        self._update({'teacher_id': teacher_id}, updates)

    def delete_teacher(self, teacher_id: str) -> None:
        self._delete({'teacher_id': teacher_id})
