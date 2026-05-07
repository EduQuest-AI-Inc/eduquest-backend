from typing import Any, Dict, List, Optional

from data_access.base_dao import SupabaseBaseDAO


class PeriodDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('period')

    def add_period(self, period) -> None:
        self._insert({
            'period_id': period.period_id,
            'owner_id': period.owner_id,
            'vector_store_id': period.vector_store_id,
            'name': period.name,
            'file_urls': getattr(period, 'file_urls', []),
            'canvas_course_id': getattr(period, 'canvas_course_id', None),
            'canvas_course_name': getattr(period, 'canvas_course_name', None),
            'start_date': period.start_date.isoformat() if period.start_date else None,
            'end_date': period.end_date.isoformat() if period.end_date else None,
            'grade_level': getattr(period, 'grade_level', None),
            'mastery_threshold': getattr(period, 'mastery_threshold', None),
            'course_description': getattr(period, 'course_description', None),
            'course_metadata': period.course_metadata.model_dump() if period.course_metadata else None,
            'file_vector_store_ids': getattr(period, 'file_vector_store_ids', []),
            'processing_status': getattr(period, 'processing_status', 'pending'),
        })

    def get_period_by_id(self, period_id: str) -> Optional[dict]:
        return self._select_by_id('period_id', period_id)

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> None:
        self._update({'period_id': period_id}, updates)

    def update_file_urls(self, period_id: str, file_urls: list) -> None:
        self._update({'period_id': period_id}, {'file_urls': file_urls})

    def delete_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})

    def get_periods_by_owner_id(self, owner_id: str) -> List:
        return self._select_eq('owner_id', owner_id)

    def update_status(self, period_id: str, status: str) -> None:
        self._update({'period_id': period_id}, {'status': status})
