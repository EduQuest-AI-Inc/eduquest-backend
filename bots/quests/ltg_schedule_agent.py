import asyncio
import logging
from typing import Optional

from agents import Agent, Runner, FileSearchTool, Tool, trace
from pydantic import BaseModel, Field

from bots.model_config import LTG_SCHEDULE_MODEL

logger = logging.getLogger(__name__)


class WeekQuest(BaseModel):
    week: int = Field(description="The week number this quest name applies to")
    quest_name: str = Field(
        description="A concrete, action-oriented quest name (max 15 words, starts with a verb)"
    )


class ScheduleOutput(BaseModel):
    quests: list[WeekQuest] = Field(
        description="One quest entry per curriculum week, in week order"
    )


_SYSTEM_INSTRUCTIONS = """\
You are a Quest Designer for EduQuest. Your job is to turn a student's chosen long-term goal
into a week-by-week sequence of actionable quest names for a school course.

RULES:
- Produce EXACTLY one quest name per week. The number of quests you return must equal the
  number of weeks in the schedule you are given — no more, no fewer.
- Each quest name must be 15 words or fewer.
- Every quest name must start with an action verb (e.g. Build, Design, Analyze, Create,
  Investigate, Apply, Compare, Draft, Prototype, Evaluate).
- Each quest name must use that week's skills as the METHOD or VEHICLE for doing something
  that moves toward the long-term goal.
- The full sequence of quest names, completed in order, should constitute a coherent
  progression toward the long-term goal — early weeks lay groundwork, later weeks apply
  and synthesize.
- Quest names should be concrete deliverables, not vague descriptions
  (e.g. "Build a budget spreadsheet using linear equations" not "Practice math").
- Connect the student's interests to the quest names where natural, but do not force it.
- Do not reference week numbers in the quest name itself.
- Do not repeat the same verb or quest framing across consecutive weeks.
"""


def _build_prompt(student: dict, goal_text: str, schedule: list[dict]) -> str:
    def _fmt(val) -> str:
        if isinstance(val, list):
            return ", ".join(str(v) for v in val) if val else "not specified"
        return str(val) if val else "not specified"

    week_lines = [
        f"  Week {entry.get('Week', '?')} — Skills: {entry.get('Skills', 'not specified')}"
        for entry in schedule
    ]

    return (
        f"Long-Term Goal: {goal_text}\n\n"
        f"Weekly Skills Schedule:\n" + "\n".join(week_lines) + "\n\n"
        f"Student Profile:\n"
        f"  Interests: {_fmt(student.get('interest'))}\n"
        f"  Strengths: {_fmt(student.get('strength'))}\n"
        f"  Grade: {student.get('grade', 'not specified')}\n\n"
        f"Generate exactly {len(schedule)} quest names — one per week in the order above — "
        f"that together form a coherent progression toward the long-term goal."
    )


class LTGScheduleAgent:
    """
    Generates goal-aligned quest names for each curriculum week.

    Runs between curriculum assembly and HWAgent. Takes the student's chosen
    long-term goal and weekly skills schedule, outputs one concrete action-oriented
    quest name per week. Together, completing all quests achieves the LTG.

    Threads previous_response_id from the LTG conversation so the model has full
    context of the student's goal discussion.
    """

    def __init__(
        self,
        student: dict,
        period: dict,
        schedule: list[dict],
        goal_text: str,
        previous_response_id: Optional[str] = None,
    ) -> None:
        self.student = student
        self.period = period
        self.schedule = schedule
        self.goal_text = goal_text
        self.previous_response_id = previous_response_id

        vector_store_id = period.get("vector_store_id")
        tools: list[Tool] = [FileSearchTool(vector_store_ids=[vector_store_id])] if vector_store_id else []

        self._agent = Agent(
            name="LTG Schedule Designer",
            instructions=_SYSTEM_INSTRUCTIONS,
            model=LTG_SCHEDULE_MODEL,
            output_type=ScheduleOutput,
            tools=tools,
        )

    async def _run_async(self) -> ScheduleOutput:
        with trace("ltg_schedule_generation"):
            prompt = _build_prompt(self.student, self.goal_text, self.schedule)

            run_kwargs: dict = {}
            if self.previous_response_id:
                run_kwargs["previous_response_id"] = self.previous_response_id

            result = await Runner.run(self._agent, prompt, **run_kwargs)  # type: ignore[arg-type]
            output: ScheduleOutput = result.final_output

            if len(output.quests) != len(self.schedule):
                logger.warning(
                    "LTGScheduleAgent returned %d quest names but expected %d — enrichment will be partial.",
                    len(output.quests),
                    len(self.schedule),
                )
            return output

    def run(self) -> ScheduleOutput:
        return asyncio.run(self._run_async())
