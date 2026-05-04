import logging
from typing import Optional

from data_access.period_schedule_dao import PeriodScheduleDAO
from data_access.period_dao import PeriodDAO
from integrations import openai_vector_store
from models.period_schedule import PeriodSchedule
from bots.provider import get_bot_provider

logger = logging.getLogger(__name__)


class PeriodScheduleService:
    """Service for managing period schedules."""

    def __init__(self) -> None:
        self.period_schedule_dao = PeriodScheduleDAO()
        self.period_dao = PeriodDAO()

    def _verify_period_ownership(self, period_id: str, user_id: str) -> dict:
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        if period.get("owner_id") != user_id:
            raise PermissionError("Not authorized to access this period")
        return period

    def generate_and_save_schedule(self, period_id: str, user_id: str, course_description: Optional[str] = None) -> dict:
        period = self._verify_period_ownership(period_id, user_id)

        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise ValueError("Period does not have a vector store configured")
        course_name = period.get("name", "Course")

        # Only search files if any were actually uploaded — empty vector stores cause API errors
        file_urls = period.get("file_urls") or []
        agent_vector_store_id = vector_store_id if file_urls else None

        # Prefer request-time description; fall back to what was stored at period creation
        course_description = course_description or period.get("course_description")

        if not file_urls and not course_description:
            raise ValueError("Provide course materials or a description of what students should learn.")

        # Generate schedule using the agent
        agent = get_bot_provider().create_schedule_agent(
            vector_store_id=agent_vector_store_id,
            course_name=course_name,
            start_date=period.get("start_date"),
            end_date=period.get("end_date"),
            course_description=course_description,
        )
        schedule_dict = agent.run_and_get_json()

        # Upload schedule to vector store
        schedule_openai_file_id = self._upload_schedule_to_vector_store(
            vector_store_id, schedule_dict
        )

        # Create or update period_schedule record
        existing = self.period_schedule_dao.get_by_period_id(period_id)
        if existing:
            # Delete old file from vector store if it exists
            if existing.schedule_openai_file_id:
                self._delete_file_from_vector_store(
                    vector_store_id, existing.schedule_openai_file_id
                )
            # Update existing record
            self.period_schedule_dao.update_period_schedule(period_id, {
                "schedule_openai_file_id": schedule_openai_file_id,
                "schedule_json": schedule_dict
            })
        else:
            # Create new record
            period_schedule = PeriodSchedule(
                period_id=period_id,
                schedule_json=schedule_dict,
                schedule_openai_file_id=schedule_openai_file_id,
                quest_enabled_weeks=[]
            )
            self.period_schedule_dao.add_period_schedule(period_schedule)

        return {
            "schedule": schedule_dict,
            "schedule_openai_file_id": schedule_openai_file_id
        }

    def get_schedule(self, period_id: str, user_id: str) -> dict | None:
        self._verify_period_ownership(period_id, user_id)

        # Get period schedule record
        period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if not period_schedule:
            return None

        return {
            "schedule": period_schedule.schedule_json or {},
            "quest_enabled_weeks": period_schedule.quest_enabled_weeks,
            "last_updated_at": period_schedule.last_updated_at,
        }

    def save_schedule_and_quest_weeks(
        self,
        period_id: str,
        user_id: str,
        schedule_dict: dict,
        quest_enabled_weeks: list,
    ) -> dict:
        period = self._verify_period_ownership(period_id, user_id)
        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise ValueError("Period does not have a vector store configured")

        period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if not period_schedule:
            raise ValueError("No schedule exists for this period. Generate one first.")

        if not quest_enabled_weeks:
            raise ValueError("At least one quest-enabled week is required")

        # Normalize quest weeks to unique sorted ints
        normalized_weeks = sorted({int(v) for v in quest_enabled_weeks if str(v).lstrip("-").isdigit()})

        old_file_id = period_schedule.schedule_openai_file_id
        new_file_id = self._upload_schedule_to_vector_store(vector_store_id, schedule_dict)

        if old_file_id:
            self._delete_file_from_vector_store(vector_store_id, old_file_id)

        self.period_schedule_dao.update_period_schedule(period_id, {
            "schedule_openai_file_id": new_file_id,
            "schedule_json": schedule_dict,
            "quest_enabled_weeks": normalized_weeks,
        })

        return {
            "message": "Schedule saved successfully",
            "schedule_openai_file_id": new_file_id,
            "quest_enabled_weeks": normalized_weeks,
        }

    def _upload_schedule_to_vector_store(self, vector_store_id: str, schedule_dict: dict) -> str:
        return openai_vector_store.upload_json(vector_store_id, schedule_dict)

    def _delete_file_from_vector_store(self, vector_store_id: str, file_id: str) -> None:
        openai_vector_store.delete_file(vector_store_id, file_id)
