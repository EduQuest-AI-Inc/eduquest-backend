from typing import Optional

from data_access.lesson_dao import LessonDAO
from data_access.lesson_pptx_dao import LessonPptxDAO


class LessonsService:
    def __init__(self, lesson_dao=None, lesson_pptx_dao=None, jwt: str | None = None) -> None:
        self.lesson_dao = lesson_dao or LessonDAO(jwt=jwt)
        self.lesson_pptx_dao = lesson_pptx_dao or LessonPptxDAO(jwt=jwt)

    def get_latest_done_pptx(self, lesson_id: str) -> Optional[dict]:
        return self.lesson_pptx_dao.get_latest_done(lesson_id)

    def get_lesson_by_id(self, lesson_id: str) -> Optional[dict]:
        return self.lesson_dao.get_by_lesson_id(lesson_id)

    def get_pptx_by_lesson_id(self, lesson_id: str) -> Optional[dict]:
        return self.lesson_pptx_dao.get_by_lesson_id(lesson_id)

    def get_pptx_by_period(self, period_id: str) -> list:
        return self.lesson_pptx_dao.get_by_period(period_id)

    def get_lessons_by_period(self, period_id: str) -> list:
        return self.lesson_dao.get_lessons_by_period(period_id)
