import re
import uuid
from typing import Optional

from data_access.period_dao import PeriodDAO
from models.period import Period


class PeriodManagementService:
    """Owns period lifecycle: creation, listing, and file updates for teachers and parents."""

    def __init__(self) -> None:
        self.period_dao = PeriodDAO()

    def generate_period_id(self, course_name: str) -> str:
        clean_course = re.sub(r'[^a-zA-Z0-9]', '', course_name).upper()[:8]
        random_part1 = str(uuid.uuid4())[:4].upper()
        random_part2 = str(uuid.uuid4())[:4].upper()
        return f"{clean_course}-{random_part1}-{random_part2}"

    def create_period(
        self,
        course: str,
        user_id: str,
        vector_store_id: str,
        file_urls: list,
        canvas_course_id: Optional[str] = None,
        canvas_course_name: Optional[str] = None,
    ) -> dict:
        period_id = self.generate_period_id(course)
        existing = self.period_dao.get_period_by_id(period_id)
        attempts = 0
        while existing and attempts < 5:
            period_id = self.generate_period_id(course)
            existing = self.period_dao.get_period_by_id(period_id)
            attempts += 1
        if existing:
            raise ValueError("Unable to generate unique period ID")

        new_period = Period(
            period_id=period_id,
            name=course,
            owner_id=user_id,
            vector_store_id=vector_store_id,
            file_urls=file_urls,
            canvas_course_id=canvas_course_id,
            canvas_course_name=canvas_course_name,
        )
        self.period_dao.add_period(new_period)
        return new_period.to_item()

    def update_file_urls(self, period_id: str, file_urls: list) -> None:
        self.period_dao.update_file_urls(period_id, file_urls)

    def get_periods_by_owner(self, user_id: str) -> list:
        return self.period_dao.get_periods_by_owner_id(user_id)

    def get_period_by_id(self, period_id: str) -> Optional[dict]:
        return self.period_dao.get_period_by_id(period_id)

    def get_vector_store_id(self, period_id: str) -> str:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        return period['vector_store_id']
