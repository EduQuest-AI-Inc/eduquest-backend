import re
import uuid
from typing import Optional

from data_access.period_dao import PeriodDAO
from data_access.period_schedule_dao import PeriodScheduleDAO
from integrations import openai_vector_store
from integrations.s3_service import delete_files_from_s3
from models.period import Period


class PeriodManagementService:
    """Owns period lifecycle: creation, listing, and file updates for teachers and parents."""

    def __init__(self) -> None:
        self.period_dao = PeriodDAO()
        self.period_schedule_dao = PeriodScheduleDAO()

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
        canvas_course_id: Optional[int] = None,
        canvas_course_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        processing_status: str = "pending",
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
            start_date=start_date,
            end_date=end_date,
            course_description=course_description,
            processing_status=processing_status,
        )
        self.period_dao.add_period(new_period)
        return new_period.to_item()

    def update_file_urls(self, period_id: str, file_urls: list) -> None:
        self.period_dao.update_file_urls(period_id, file_urls)

    def update_processing_status(self, period_id: str, status: str) -> None:
        self.period_dao.update_period(period_id, {"processing_status": status})

    def update_vector_store_id(self, period_id: str, vector_store_id: str) -> None:
        self.period_dao.update_period(period_id, {"vector_store_id": vector_store_id})

    def update_file_vector_store_ids(self, period_id: str, file_vector_store_ids: list) -> None:
        self.period_dao.update_period(period_id, {"file_vector_store_ids": file_vector_store_ids})

    def get_periods_by_owner(self, user_id: str) -> list:
        periods = self.period_dao.get_periods_by_owner_id(user_id)
        for period in periods:
            schedule = self.period_schedule_dao.get_by_period_id(period['period_id'])
            period['has_schedule'] = schedule is not None and len(schedule.quest_enabled_weeks) > 0
        return periods

    def get_period_by_id(self, period_id: str) -> Optional[dict]:
        return self.period_dao.get_period_by_id(period_id)

    def get_vector_store_id(self, period_id: str) -> str:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        return period['vector_store_id']

    def delete_period(self, period_id: str, user_id: str) -> None:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        if period.get("owner_id") != user_id:
            raise PermissionError("Not authorized to delete this period")
        vector_store_id = period.get("vector_store_id")
        if vector_store_id:
            openai_vector_store.delete_store(vector_store_id)
        file_keys = [u for u in (period.get("file_urls") or []) if not u.startswith("local/")]
        if file_keys:
            delete_files_from_s3(file_keys)
        self.period_dao.delete_period(period_id)
