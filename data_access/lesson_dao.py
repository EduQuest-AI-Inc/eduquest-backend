from typing import Any

from data_access.base_dao import SupabaseBaseDAO
from models.lesson import Lesson


class LessonDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('lesson', jwt=jwt)

    def insert_lesson(self, lesson: Lesson) -> str:
        row = self._insert(lesson.to_item())
        return row.get('lesson_id', '')

    def get_lessons_by_period(self, period_id: str) -> list[dict[str, Any]]:
        return self._select_eq('period_id', period_id)

    def get_by_lesson_id(self, lesson_id: str) -> dict[str, Any] | None:
        return self._select_by_id('lesson_id', lesson_id)

    def update_lesson(self, lesson_id: str, fields: dict[str, Any]) -> None:
        self._update({'lesson_id': lesson_id}, fields)

    def delete_all_for_period(self, period_id: str) -> None:
        self._delete({'period_id': period_id})
