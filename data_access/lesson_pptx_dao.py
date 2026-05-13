from typing import Any, Optional

from data_access.base_dao import SupabaseBaseDAO
from models.lesson_pptx import LessonPptx


class LessonPptxDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('lesson_pptx')

    def insert(self, record: LessonPptx) -> dict[str, Any]:
        return self._insert(record.to_item())

    def update_status(self, pptx_id: str, fields: dict[str, Any]) -> None:
        self._update({'pptx_id': pptx_id}, fields)

    def get_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def get_by_lesson_id(self, lesson_id: str) -> Optional[dict[str, Any]]:
        return self._select_by_id('lesson_id', lesson_id)

    def get_latest_done(self, lesson_id: str) -> Optional[dict[str, Any]]:
        response = self._execute(
            self._table()
            .select('*')
            .eq('lesson_id', lesson_id)
            .eq('status', 'done')
            .order('created_at', desc=True)
            .limit(1)
            .maybe_single()
        )
        if response is None or response.data is None:
            return None
        return response.data
