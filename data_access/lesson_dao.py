from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.lesson import Lesson


class LessonDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('lesson')

    def insert_lesson(self, lesson: Lesson) -> str:
        row = self._insert(lesson.to_item())
        return row.get('lesson_id', '')

    def get_lessons_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def update_lesson(self, lesson_id: str, fields: dict[str, Any]) -> None:
        self._update({'lesson_id': lesson_id}, fields)
