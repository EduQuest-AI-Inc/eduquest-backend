from typing import List, Dict, Any

from data_access.supabase.base_dao import SupabaseBaseDAO


class EnrollmentDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('enrollment')

    def add_enrollment(self, enrollment) -> None:
        self._insert({
            'enrollment_id': enrollment.enrollment_id,
            'user_id': enrollment.user_id,
            'period_id': enrollment.period_id,
            'semester': enrollment.semester,
            'enrolled_at': enrollment.enrolled_at,
        })

    def get_enrollment_by_period(self, period_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def get_enrollments_by_period(self, period_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def get_enrollments_by_student(self, user_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('user_id', user_id)

    def update_enrollment(self, user_id: str, period_id: str, updates: Dict[str, Any]) -> None:
        self._update({'user_id': user_id, 'period_id': period_id}, updates)

    def delete_enrollment(self, user_id: str, period_id: str) -> None:
        self._delete({'user_id': user_id, 'period_id': period_id})
