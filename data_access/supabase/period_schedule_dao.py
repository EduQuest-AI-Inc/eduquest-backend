from typing import Dict, Any, Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class PeriodScheduleDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__('period_schedule')

    def add_period_schedule(self, period_schedule) -> None:
        self._insert({
            'period_id': period_schedule.period_id,
            'teacher_id': period_schedule.teacher_id,
            'vector_store_id': period_schedule.vector_store_id,
            'schedule_s3_key': getattr(period_schedule, 'schedule_s3_key', None),
            'schedule_json': getattr(period_schedule, 'schedule_json', None),
            'schedule_openai_file_id': getattr(period_schedule, 'schedule_openai_file_id', None),
            'quest_enabled_weeks': getattr(period_schedule, 'quest_enabled_weeks', []),
        })

    def get_by_period_id(self, period_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('period_id', period_id)

    def update_period_schedule(self, period_id: str, updates: Dict[str, Any]) -> None:
        updates['last_updated_at'] = datetime.now(timezone.utc).isoformat()
        self._update({'period_id': period_id}, updates)

    def delete_period_schedule(self, period_id: str) -> None:
        self._delete({'period_id': period_id})
