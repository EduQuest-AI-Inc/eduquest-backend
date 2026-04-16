from typing import Dict, Any, Optional, List

from data_access.supabase.base_dao import SupabaseBaseDAO


class PeriodDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('period')

    def add_period(self, period) -> None:
        # Supabase `period` schema uses owner_id + owner_type; the legacy
        # DynamoDB `teacher_id` column was dropped. Do NOT include it here
        # or PostgREST returns PGRST204 ("column not found in schema cache").
        self._insert({
            'period_id': period.period_id,
            'owner_id': period.owner_id,
            'owner_type': getattr(period, 'owner_type', 'teacher'),
            'vector_store_id': period.vector_store_id,
            'course': period.course,
            'file_urls': getattr(period, 'file_urls', []),
            'canvas_api_url': getattr(period, 'canvas_api_url', None),
            'canvas_api_key': getattr(period, 'canvas_api_key', None),
            'canvas_course_id': getattr(period, 'canvas_course_id', None),
            'canvas_course_name': getattr(period, 'canvas_course_name', None),
            'parent_id': getattr(period, 'parent_id', None),
        })

    def get_period_by_id(self, period_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('period_id', period_id)

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> None:
        self._update({'period_id': period_id}, updates)

    def delete_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})

    def get_periods_by_owner_id(self, owner_id: str) -> List:
        return self._select_eq('owner_id', owner_id)

    def get_periods_by_teacher_id(self, teacher_id: str) -> List:
        return self._select_eq('owner_id', teacher_id)

    def get_periods_by_parent_id(self, parent_id: str) -> List:
        return self._select_eq('owner_id', parent_id)
