import re
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from data_access.enrollment_dao import EnrollmentDAO
from data_access.period_dao import PeriodDAO
from exceptions.not_found_error import NotFoundError
from exceptions.permission_error import PermissionError
from exceptions.validation_error import ValidationError
from integrations import openai_vector_store
from integrations.s3_service import delete_files_from_s3
from models.enrollment import Enrollment
from models.period import CourseMetadata, Period


class PeriodManagementService:
    """Owns period lifecycle: creation, listing, and file updates for teachers and parents."""

    def __init__(self, period_dao=None, enrollment_dao=None, jwt: str | None = None) -> None:
        self.period_dao = period_dao or PeriodDAO(jwt=jwt)
        self.enrollment_dao = enrollment_dao or EnrollmentDAO(jwt=jwt)

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
        grade_level: Optional[str] = None,
        mastery_threshold: Optional[float] = None,
        course_description: Optional[str] = None,
        course_metadata: Optional[CourseMetadata] = None,
        processing_status: str = "pending",
        status: str = "pending",
        is_summer_quest: bool = False,
    ) -> dict:
        period_id = self.generate_period_id(course)
        existing = self.period_dao.get_period_by_id(period_id)
        attempts = 0
        while existing and attempts < 5:
            period_id = self.generate_period_id(course)
            existing = self.period_dao.get_period_by_id(period_id)
            attempts += 1
        if existing:
            raise ValidationError("Unable to generate unique period ID")

        new_period = Period(
            period_id=period_id,
            name=course,
            owner_id=user_id,
            vector_store_id=vector_store_id,
            file_urls=file_urls,
            canvas_course_id=canvas_course_id,
            canvas_course_name=canvas_course_name,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
            grade_level=grade_level,
            mastery_threshold=mastery_threshold,
            course_description=course_description,
            course_metadata=course_metadata,
            processing_status=processing_status,
            status=status,
            is_summer_quest=is_summer_quest,
        )
        self.period_dao.add_period(new_period)

        if is_summer_quest:
            enrollment = Enrollment(
                user_id=user_id,
                period_id=period_id,
                semester="Summer",
                enrolled_at=datetime.now(timezone.utc).isoformat(),
            )
            self.enrollment_dao.add_enrollment(enrollment)

        return new_period.to_item()

    def update_status(self, period_id: str, status: str) -> None:
        self.period_dao.update_status(period_id, status)

    def update_setup(self, period_id: str, fields: dict) -> Optional[dict]:
        self.period_dao.update_period(period_id, fields)
        return self.period_dao.get_period_by_id(period_id)

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
        return [self._enrich_period(p) for p in periods]

    def get_period_by_id(self, period_id: str) -> Optional[dict]:
        period = self.period_dao.get_period_by_id(period_id)
        return self._enrich_period(period) if period else None

    @staticmethod
    def _enrich_period(period: dict) -> dict:
        period['has_curriculum'] = period.get('status') in ('draft', 'approved')
        return period

    def get_vector_store_id(self, period_id: str) -> str:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Period not found")
        return period['vector_store_id']

    def delete_period(self, period_id: str, user_id: str, period: dict | None = None) -> None:
        period = period or self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Period not found")
        if period.get("owner_id") != user_id:
            raise PermissionError("Not authorized to delete this period")
        is_fork = bool(period.get("forked_from_period_id"))
        if is_fork:
            # Assets belong to the original class — never delete them from a fork
            pass
        else:
            # Block deletion if any forks still reference this class
            if self.period_dao.get_forks_by_period(period_id):
                raise ValidationError(
                    "Cannot delete a class that has active forks in the marketplace. "
                    "Unpublish the marketplace listing first, then ask fork owners to delete their copies."
                )
            vector_store_id = period.get("vector_store_id")
            if vector_store_id:
                openai_vector_store.delete_store(vector_store_id)
            file_keys = [u for u in (period.get("file_urls") or []) if not u.startswith("local/")]
            if file_keys:
                delete_files_from_s3(file_keys)
        self.period_dao.delete_period(period_id)

    def archive_period(self, period_id: str, user_id: str, period: dict | None = None) -> dict:
        period = period or self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Period not found")
        if period.get("owner_id") != user_id:
            raise PermissionError("Not authorized to archive this period")
        self.period_dao.archive_period(period_id)
        updated = self.period_dao.get_period_by_id(period_id)
        if not updated:
            raise NotFoundError("Period not found after archiving")
        return self._enrich_period(updated)

    def unarchive_period(self, period_id: str, user_id: str, period: dict | None = None) -> dict:
        period = period or self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Period not found")
        if period.get("owner_id") != user_id:
            raise PermissionError("Not authorized to unarchive this period")
        self.period_dao.unarchive_period(period_id)
        updated = self.period_dao.get_period_by_id(period_id)
        if not updated:
            raise NotFoundError("Period not found after unarchiving")
        return self._enrich_period(updated)
