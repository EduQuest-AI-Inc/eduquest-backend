import logging
import sys
import os
from typing import Optional
import math

logger = logging.getLogger(__name__)

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date, timedelta
from pydantic import BaseModel, Field
from typing import List
from agents import Agent, Runner, FileSearchTool, trace
from openai import OpenAI
import asyncio
import json
import tempfile

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ScheduleWeekItem(BaseModel):
    """Schema for a single week in the period schedule."""
    week_number: int = Field(description="Week number (1, 2, 3, etc.)")
    start_date: str = Field(description="Start date of the week (or 'Not specified' if unknown)")
    end_date: str = Field(description="End date of the week (or 'Not specified' if unknown)")
    lessons: List[str] = Field(description="List of lesson titles and short descriptions for this week")
    skills: List[str] = Field(description="List of measurable skills students will learn")


class PeriodScheduleSchema(BaseModel):
    """Schema for the full period schedule output."""
    weeks: List[ScheduleWeekItem] = Field(description="List of weeks in the semester schedule")


class PeriodScheduleAgent:
    """
    Agent that generates a period-level semester schedule.
    This is teacher/period scoped (not student-specific).
    """


    def __init__(
        self,
        vector_store_id: str,
        course_name: str = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
    ) -> None:
        self.vector_store_id = vector_store_id
        self.course_description = course_description
        self.course_name = course_name or "the course"

        # Compute week count and calendar from dates when provided
        num_weeks = 18
        calendar_section = "- Missing term dates → use \"Not specified\" for start_date/end_date"
        if start_date and end_date:
            try:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
                num_weeks = max(1, math.ceil((end - start).days / 7))
                rows = []
                for w in range(1, num_weeks + 1):
                    week_start = start + timedelta(weeks=w - 1)
                    week_end = week_start + timedelta(days=6)
                    rows.append(f"  Week {w}: {week_start.isoformat()} to {week_end.isoformat()}")
                calendar_section = (
                    "The class runs for EXACTLY {num_weeks} weeks. Use these exact dates:\n"
                    "{rows}\n"
                    "Copy the start_date and end_date exactly from this table for each week."
                ).format(num_weeks=num_weeks, rows="\n".join(rows))
            except ValueError:
                pass

        instructions = f"""You are "Weekly Course Schedule Architect," an AI agent that builds a week-by-week instructional schedule from course materials.

MISSION
Transform course inputs into a weekly schedule with:
- Week number (integer starting from 1)
- Week start date
- Week end date
- Lessons (list of what is taught that week)
- Skills (list of measurable outcomes)

Your output must be accurate to the provided materials and must not invent content not present in the inputs.

OPERATING PRINCIPLES
1) Evidence-first: Prefer explicit evidence from the provided course materials.
2) Weekly clarity: Each week must have a coherent theme, manageable lessons, and skills stated as observable outcomes.
3) Non-hallucination: Do not create readings, videos, quizzes, or policies that aren't referenced.
4) The schedule must have EXACTLY {num_weeks} weeks — no more, no fewer.

TERM CALENDAR
{calendar_section}

OUTPUT FORMAT
Return a JSON object with a "weeks" array. Each week has:
- week_number: integer (1, 2, 3, ...)
- start_date: string (date or "Not specified")
- end_date: string (date or "Not specified")
- lessons: list of strings (3-8 lesson titles/descriptions per week)
- skills: list of strings

PROCESS
1. Search the course materials to understand the curriculum structure.
2. Identify modules, units, assignments, and their sequence.
3. Allocate content across exactly {num_weeks} weeks based on module order.
4. For each week, extract lesson topics and derive measurable skills.
5. Ensure every major module appears in some week.

HANDLING MISSING INFO
- Missing content for a week → describe as "Review/Catch-up week" or similar"""

        tools = (
            [FileSearchTool(vector_store_ids=[self.vector_store_id])]
            if self.vector_store_id
            else []
        )
        self.agent = Agent(
            name="Period Schedule Agent",
            instructions=instructions,
            model="gpt-5",
            tools=tools,  # type: ignore[arg-type]
            output_type=PeriodScheduleSchema
        )

    async def _run_async(self) -> PeriodScheduleSchema:
        """Run the agent asynchronously."""
        if self.vector_store_id:
            prompt = f"""Please create a weekly semester schedule for {self.course_name} based on the course materials in the vector store.

Search the course materials to understand:
- What modules/units exist
- What topics are covered
- Any assignments, quizzes, or due dates
- The sequence and structure of the curriculum

Then produce a complete weekly schedule covering the entire semester."""
        else:
            prompt = f"""Please create a weekly semester schedule for {self.course_name}.

No course files were uploaded. Use the following teacher-provided description as your sole curriculum source:

{self.course_description}

Do not invent content beyond what is described above. Base the schedule entirely on this description."""

        with trace("period_schedule_generation"):
            result = await Runner.run(
                self.agent,
                prompt
            )
        return result.final_output

    def run(self) -> PeriodScheduleSchema:
        """Run the agent synchronously and return the schedule."""
        return asyncio.run(self._run_async())

    def run_and_get_json(self) -> dict:
        """Run the agent and return the schedule as a JSON-serializable dict."""
        schedule = self.run()
        return schedule.model_dump()


class PeriodScheduleService:
    """
    Service for managing period schedules including S3 and vector store operations.
    """

    def __init__(self, period_id: str, vector_store_id: str) -> None:
        self.period_id = period_id
        self.vector_store_id = vector_store_id
        self.schedule_openai_file_id: Optional[str] = None

    def generate_schedule(self, course_name: Optional[str] = None) -> dict:
        """
        Generate a new schedule using the agent.

        Args:
            course_name: Optional course name for context.

        Returns:
            dict: The generated schedule as a dictionary.
        """
        agent = PeriodScheduleAgent(
            vector_store_id=self.vector_store_id,
            course_name=course_name
        )
        return agent.run_and_get_json()

    def upload_schedule_to_vector_store(self, schedule_dict: dict) -> str:
        """
        Upload schedule JSON to the vector store.

        Args:
            schedule_dict: The schedule as a dictionary.

        Returns:
            str: The OpenAI file ID of the uploaded schedule.
        """
        # Create a temp file with the schedule JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(schedule_dict, f, indent=2)
            temp_path = f.name

        try:
            # Upload file to OpenAI
            with open(temp_path, 'rb') as f:
                file_response = client.files.create(
                    file=f,
                    purpose="assistants"
                )

            # Attach to vector store
            client.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=file_response.id
            )

            self.schedule_openai_file_id = file_response.id
            return file_response.id

        finally:
            # Cleanup temp file
            os.unlink(temp_path)

    def replace_schedule_in_vector_store(self, schedule_dict: dict, old_file_id: Optional[str] = None) -> str:
        """
        Replace the schedule in the vector store.

        Args:
            schedule_dict: The new schedule as a dictionary.
            old_file_id: The old file ID to delete (optional).

        Returns:
            str: The new OpenAI file ID.
        """
        # Delete old file if provided
        if old_file_id:
            try:
                client.vector_stores.files.delete(
                    vector_store_id=self.vector_store_id,
                    file_id=old_file_id
                )
            except Exception as e:
                logger.warning("Failed to delete old schedule file %s: %s", old_file_id, e)

        # Upload new schedule
        return self.upload_schedule_to_vector_store(schedule_dict)
