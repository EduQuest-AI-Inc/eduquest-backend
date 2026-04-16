import json
import tempfile
import os
from datetime import datetime, timezone
from openai import OpenAI
if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.period_schedule_dao import PeriodScheduleDAO
    from data_access.supabase.period_dao import PeriodDAO
else:
    from data_access.period_schedule_dao import PeriodScheduleDAO
    from data_access.period_dao import PeriodDAO
from models.period_schedule import PeriodSchedule
from EQ_agents.schedule_agent import PeriodScheduleAgent
from s3 import upload_file_to_s3

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class PeriodScheduleService:
    """Service for managing period schedules."""

    def __init__(self):
        self.period_schedule_dao = PeriodScheduleDAO()
        self.period_dao = PeriodDAO()

    def generate_and_save_schedule(self, period_id: str, teacher_id: str) -> dict:
        """
        Generate a schedule for a period and save it to DB, S3, and vector store.

        Args:
            period_id: The period ID.
            teacher_id: The teacher ID (for authorization).

        Returns:
            dict: The generated schedule and metadata.
        """
        # Get period to verify ownership and get vector_store_id
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        if period.get("owner_id", period.get("teacher_id")) != teacher_id:
            raise PermissionError("Not authorized to access this period")

        vector_store_id = period.get("vector_store_id")
        course_name = period.get("course", "Course")

        # Generate schedule using the agent
        agent = PeriodScheduleAgent(
            vector_store_id=vector_store_id,
            course_name=course_name
        )
        schedule_dict = agent.run_and_get_json()

        # Save schedule to S3
        schedule_s3_key = self._save_schedule_to_s3(period_id, schedule_dict)

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
                "schedule_s3_key": schedule_s3_key,
                "schedule_openai_file_id": schedule_openai_file_id,
                "schedule_json": schedule_dict
            })
        else:
            # Create new record
            period_schedule = PeriodSchedule(
                period_id=period_id,
                teacher_id=teacher_id,
                vector_store_id=vector_store_id,
                schedule_s3_key=schedule_s3_key,
                schedule_json=schedule_dict,
                schedule_openai_file_id=schedule_openai_file_id,
                quest_enabled_weeks=[]
            )
            self.period_schedule_dao.add_period_schedule(period_schedule)

        return {
            "schedule": schedule_dict,
            "schedule_s3_key": schedule_s3_key,
            "schedule_openai_file_id": schedule_openai_file_id
        }

    def get_schedule(self, period_id: str, teacher_id: str) -> dict:
        """
        Get the schedule for a period.

        Args:
            period_id: The period ID.
            teacher_id: The teacher ID (for authorization).

        Returns:
            dict: The schedule data and metadata.
        """
        # Verify period ownership
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        if period.get("owner_id", period.get("teacher_id")) != teacher_id:
            raise PermissionError("Not authorized to access this period")

        # Get period schedule record
        period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if not period_schedule:
            return None

        schedule_source = None
        schedule_dict = {}
        if period_schedule.schedule_s3_key:
            # Fetch schedule from S3 (preferred when configured)
            schedule_dict = self._get_schedule_from_s3(period_schedule.schedule_s3_key)
            schedule_source = "s3"

        # Fallback to Dynamo if S3 is unavailable/misconfigured or returned empty
        if (not schedule_dict) and period_schedule.schedule_json:
            schedule_dict = period_schedule.schedule_json
            schedule_source = "dynamo"

        return {
            "schedule": schedule_dict,
            "quest_enabled_weeks": period_schedule.quest_enabled_weeks,
            "schedule_s3_key": period_schedule.schedule_s3_key,
            "last_updated_at": period_schedule.last_updated_at,
            "schedule_source": schedule_source
        }

    def update_schedule(self, period_id: str, teacher_id: str, schedule_dict: dict) -> dict:
        """
        Update the schedule for a period.

        Args:
            period_id: The period ID.
            teacher_id: The teacher ID (for authorization).
            schedule_dict: The new schedule data.

        Returns:
            dict: The updated schedule metadata.
        """
        # Verify period ownership
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        if period.get("owner_id", period.get("teacher_id")) != teacher_id:
            raise PermissionError("Not authorized to access this period")

        vector_store_id = period.get("vector_store_id")

        # Get existing period schedule
        period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if not period_schedule:
            raise ValueError("No schedule exists for this period. Generate one first.")

        old_file_id = period_schedule.schedule_openai_file_id

        # Save new schedule to S3
        schedule_s3_key = self._save_schedule_to_s3(period_id, schedule_dict)

        # Upload new schedule to vector store
        new_file_id = self._upload_schedule_to_vector_store(vector_store_id, schedule_dict)

        # Delete old file from vector store
        if old_file_id:
            self._delete_file_from_vector_store(vector_store_id, old_file_id)

        # Update DB record
        self.period_schedule_dao.update_period_schedule(period_id, {
            "schedule_s3_key": schedule_s3_key,
            "schedule_openai_file_id": new_file_id,
            "schedule_json": schedule_dict
        })

        return {
            "message": "Schedule updated successfully",
            "schedule_s3_key": schedule_s3_key,
            "schedule_openai_file_id": new_file_id
        }

    def set_quest_weeks(self, period_id: str, teacher_id: str, quest_enabled_weeks: list) -> dict:
        """
        Set which weeks have quests enabled.

        Args:
            period_id: The period ID.
            teacher_id: The teacher ID (for authorization).
            quest_enabled_weeks: List of week numbers where quests are enabled.

        Returns:
            dict: Confirmation message.
        """
        # Verify period ownership
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise ValueError("Period not found")
        if period.get("owner_id", period.get("teacher_id")) != teacher_id:
            raise PermissionError("Not authorized to access this period")

        # Normalize to unique sorted ints (frontend can send strings)
        normalized_weeks = []
        if isinstance(quest_enabled_weeks, list):
            for v in quest_enabled_weeks:
                try:
                    n = int(v)
                    normalized_weeks.append(n)
                except Exception:
                    continue
        normalized_weeks = sorted(set(normalized_weeks))

        # Get or create period schedule
        period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
        if not period_schedule:
            # Create a minimal record if none exists
            period_schedule = PeriodSchedule(
                period_id=period_id,
                teacher_id=teacher_id,
                vector_store_id=period.get("vector_store_id"),
                quest_enabled_weeks=normalized_weeks
            )
            self.period_schedule_dao.add_period_schedule(period_schedule)
        else:
            # Update existing record
            self.period_schedule_dao.update_period_schedule(period_id, {
                "quest_enabled_weeks": normalized_weeks
            })

        return {
            "message": "Quest weeks updated successfully",
            "quest_enabled_weeks": normalized_weeks
        }

    def _save_schedule_to_s3(self, period_id: str, schedule_dict: dict) -> str:
        """Save schedule JSON to S3."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(schedule_dict, f, indent=2)
            temp_path = f.name

        try:
            s3_key = upload_file_to_s3(
                temp_path,
                filename="schedule.json",
                folder=f"periods/{period_id}/schedule"
            )
            if not s3_key:
                # Fallback for local testing
                s3_key = f"periods/{period_id}/schedule/schedule.json"
            return s3_key
        finally:
            os.unlink(temp_path)

    def _get_schedule_from_s3(self, s3_key: str) -> dict:
        """Fetch schedule JSON from S3."""
        import boto3

        try:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION")
            )
            bucket_name = os.getenv("S3_BUCKET_NAME")
            if not bucket_name:
                return {}

            response = s3.get_object(Bucket=bucket_name, Key=s3_key)
            content = response['Body'].read().decode('utf-8')
            parsed = json.loads(content)
            return parsed
        except Exception as e:
            print(f"Error fetching schedule from S3: {e}")
            return {}

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

    def _delete_file_from_vector_store(self, vector_store_id: str, file_id: str):
        """Delete a file from the vector store."""
        try:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
        except Exception as e:
            print(f"Warning: Failed to delete file {file_id} from vector store: {e}")
