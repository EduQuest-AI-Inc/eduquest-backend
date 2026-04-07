from typing import List, Dict, Any

from data_access.supabase.base_dao import SupabaseBaseDAO


class EnrollmentDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('enrollment')

    def add_enrollment(self, enrollment) -> None:
        self._insert({
            'student_id': enrollment.student_id,
            'period_id': enrollment.period_id,
            'semester': enrollment.semester,
            'enrolled_at': enrollment.enrolled_at,
        })

    def get_enrollments_by_period(self, period_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def get_enrollments_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        return self._select_eq('student_id', student_id)

    def update_enrollment(self, student_id: str, period_id: str, updates: Dict[str, Any]) -> None:
        """Update an enrollment by its composite PK (student_id, period_id).

        NOTE: Signature changed from DynamoDB version which used (period_id, enrolled_at).
        """
        self._update({'student_id': student_id, 'period_id': period_id}, updates)

    def delete_enrollment(self, student_id: str, period_id: str) -> None:
        """Delete an enrollment by its composite PK (student_id, period_id).

        NOTE: Signature changed from DynamoDB version which used (period_id, enrolled_at).
        """
        self._delete({'student_id': student_id, 'period_id': period_id})
