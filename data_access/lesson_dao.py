from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.lesson import Lesson


class LessonDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('lesson')

    def insert_lesson(self, lesson: Lesson) -> None:
        self._insert(lesson.to_item())

    def get_lessons_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def update_lesson(self, period_id: str, lesson_name: str, fields: dict[str, Any]) -> None:
        self._update({'period_id': period_id, 'lesson_name': lesson_name}, fields)
