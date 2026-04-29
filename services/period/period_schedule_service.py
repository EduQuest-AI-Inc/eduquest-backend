import json
import logging
import tempfile
import os
from openai import OpenAI

from data_access.period_schedule_dao import PeriodScheduleDAO
from data_access.period_dao import PeriodDAO
from models.period_schedule import PeriodSchedule
from bots.provider import get_bot_provider

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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

    def generate_and_save_schedule(self, period_id: str, user_id: str) -> dict:
        period = self._verify_period_ownership(period_id, user_id)

        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise ValueError("Period has no vector store. Re-create the class to fix this.")
        course_name = period.get("name", "Course")

        # Only search files if any were actually uploaded — empty vector stores cause API errors
        file_urls = period.get("file_urls") or []
        agent_vector_store_id = vector_store_id if file_urls else None

        # Generate schedule using the agent
        agent = get_bot_provider().create_schedule_agent(
            vector_store_id=agent_vector_store_id,
            course_name=course_name,
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
        """Upload schedule JSON to vector store."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(schedule_dict, f, indent=2)
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                file_response = client.files.create(
                    file=f,
                    purpose="assistants"
                )

            client.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=file_response.id
            )

            return file_response.id
        finally:
            os.unlink(temp_path)

    def _delete_file_from_vector_store(self, vector_store_id: str, file_id: str) -> None:
        """Delete a file from the vector store."""
        try:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
        except Exception as e:
            logger.warning("Failed to delete file %s from vector store: %s", file_id, e)
