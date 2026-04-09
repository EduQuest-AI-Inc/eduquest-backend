from typing import Dict, Any, Optional, List

from data_access.supabase.base_dao import SupabaseBaseDAO


class PeriodDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('period')

    def add_period(self, period) -> None:
        self._insert({
            'period_id': period.period_id,
            'teacher_id': period.teacher_id,
            'vector_store_id': period.vector_store_id,
            'course': period.course,
            'file_urls': getattr(period, 'file_urls', []),
            'canvas_api_url': getattr(period, 'canvas_api_url', None),
            'canvas_api_key': getattr(period, 'canvas_api_key', None),
            'canvas_course_id': getattr(period, 'canvas_course_id', None),
            'canvas_course_name': getattr(period, 'canvas_course_name', None),
        })

    def get_period_by_id(self, period_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('period_id', period_id)

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> None:
        self._update({'period_id': period_id}, updates)

    def delete_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})

    def get_periods_by_teacher_id(self, teacher_id: str) -> List:
        # DynamoDB version used a full table scan; Postgres uses the teacher_id index
        return self._select_eq('teacher_id', teacher_id)
