from typing import Any, Dict, List, Optional

from data_access.base_dao import SupabaseBaseDAO


class PeriodDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('period', jwt=jwt)

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
            'status': getattr(period, 'status', 'pending'),
            'is_summer_quest': getattr(period, 'is_summer_quest', False),
            'forked_from_period_id': getattr(period, 'forked_from_period_id', None),
        })

    def get_period_by_id(self, period_id: str) -> Optional[dict]:
        return self._select_by_id('period_id', period_id)

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> None:
        self._update({'period_id': period_id}, updates)

    def update_file_urls(self, period_id: str, file_urls: list) -> None:
        self._update({'period_id': period_id}, {'file_urls': file_urls})

    def delete_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})

    def get_periods_by_ids(self, period_ids: List[str]) -> List[dict]:
        if not period_ids:
            return []
        response = self._execute(
            self._table().select('*').in_('period_id', period_ids)
        )
        return response.data if response.data else []

    def get_periods_by_owner_id(self, owner_id: str) -> List:
        return self._select_eq('owner_id', owner_id)

    def get_forks_by_period(self, original_period_id: str) -> List[dict]:
        return self._select_eq('forked_from_period_id', original_period_id)

    def update_status(self, period_id: str, status: str) -> None:
        self._update({'period_id': period_id}, {'status': status})

    def archive_period(self, period_id: str) -> None:
        from datetime import datetime, timezone
        self._update(
            {'period_id': period_id},
            {'archived_at': datetime.now(timezone.utc).isoformat()},
        )

    def unarchive_period(self, period_id: str) -> None:
        self._update({'period_id': period_id}, {'archived_at': None})

    def try_start_generating(self, period_id: str) -> bool:
        """Atomically transition period to 'generating' only if currently 'pending' or 'failed'.

        Returns True if the lock was acquired (status updated), False if already generating
        or in a non-triggerable state.
        """
        result = self._execute(
            self._table()
            .update({'status': 'generating'})
            .eq('period_id', period_id)
            .in_('status', ['pending', 'failed'])
        )
        return bool(result.data)

    def reset_stale_generating(self) -> int:
        """Reset all periods stuck in 'generating' to 'failed'.

        Call at server startup — any in-flight generation tasks are dead because the
        process restarted, so every 'generating' row is stale by definition.
        Returns the number of rows reset.
        """
        result = self._execute(
            self._table()
            .update({'status': 'failed'})
            .eq('status', 'generating')
        )
        return len(result.data) if result.data else 0
