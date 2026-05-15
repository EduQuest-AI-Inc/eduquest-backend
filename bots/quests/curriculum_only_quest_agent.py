"""
CurriculumOnlyQuestAgent — generates long-term goal + all quests from the curriculum alone.

No student profile (no strengths/weaknesses/interests/grade) and no LTG conversation
are required. Used exclusively for Summer Side Quests.
"""
import asyncio
import logging
import re
from typing import Any

from agents import Agent, FileSearchTool, Runner, trace
from pydantic import BaseModel, Field

from bots.model_config import (
    CURRICULUM_ONLY_INSTRUCTION_MODEL,
    CURRICULUM_ONLY_LTG_MODEL,
    CURRICULUM_ONLY_QUEST_NAME_MODEL,
    CURRICULUM_ONLY_RUBRIC_MODEL,
)
from bots.schemas.instructions import Instructions
from bots.schemas.rubric import Rubric

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic output schemas
# ---------------------------------------------------------------------------


class LongTermGoalOutput(BaseModel):
    goal_text: str = Field(
        description=(
            "A single sentence describing what completing all quests will achieve, "
            "derived from the curriculum topic and uploaded materials."
        )
    )


class WeekQuest(BaseModel):
    week: int = Field(description="The week number this quest name applies to")
    quest_name: str = Field(
        description="A concrete, action-oriented quest name (max 15 words, starts with a verb)"
    )


class QuestScheduleOutput(BaseModel):
    quests: list[WeekQuest] = Field(
        description="One quest entry per curriculum week, in week order"
    )


class IndividualQuest(BaseModel):
    Name: str
    Skills: str
    Week: int
    instructions: list[dict[str, Any]]
    rubric: dict[str, Any]


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_LTG_INSTRUCTIONS = """\
You are an educational goal designer for EduQuest. Your job is to read the uploaded
curriculum materials and write a single-sentence long-term learning goal that captures
what a student will achieve by completing the entire course.

RULES:
- Write exactly ONE sentence.
- Start with "By the end of this quest, you will…" or an equivalent forward-looking phrase.
- Be specific to the subject matter — not generic ("learn a lot").
- Reflect the full arc of the curriculum, not just the first week.
- Use plain prose: no markdown, no lists, no escape sequences.
"""

_QUEST_NAME_INSTRUCTIONS = """\
You are a Quest Designer for EduQuest. Your job is to turn a long-term learning goal
and a weekly skills schedule into a sequence of actionable quest names for a personal
learning project.

RULES:
- Produce EXACTLY one quest name per week. The number of quests must equal the number
  of weeks in the schedule — no more, no fewer.
- Each quest name must be 15 words or fewer.
- Every quest name must start with an action verb (e.g. Build, Design, Analyze, Create,
  Investigate, Apply, Compare, Draft, Prototype, Evaluate).
- Each quest name must use that week's skills as the method or vehicle for making
  progress toward the long-term goal.
- The full sequence should form a coherent progression — early weeks lay groundwork,
  later weeks apply and synthesize.
- Quest names should be concrete deliverables, not vague descriptions
  (e.g. "Build a budget spreadsheet using linear equations" not "Practice math").
- Do not reference week numbers in the quest name itself.
- Do not repeat the same verb or quest framing across consecutive weeks.
"""

_INSTRUCTION_INSTRUCTIONS = """\
You create detailed step-by-step instructions for a learning quest.

Create 4-7 steps that:
- Are clear and actionable
- Align with the quest skills provided
- Are grounded in the uploaded curriculum materials

IMPORTANT formatting rules for each step's text:
- Write plain prose sentences only
- No markdown (no *, **, #, -, ^, >)
- No escape sequences (no \\n, \\r, \\t)
- No numbered prefixes in the text (the step number is stored separately)
"""

_RUBRIC_INSTRUCTIONS = """\
You create grading rubrics for quests with multiple criteria.

Create a rubric with 3-4 specific assessment criteria, each with Score_0 through Score_5
descriptions.

IMPORTANT: Create a list of criteria_list where each item has:
- name: The name of the criterion (e.g., "Accuracy", "Understanding", "Presentation")
- scale: An object with Score_0, Score_1, Score_2, Score_3, Score_4, Score_5 fields

For each criterion, provide specific descriptions for what constitutes each score level
(0-5) for THAT particular aspect. Make each criterion's scoring descriptions specific to
what you are evaluating in that area. Each score level should clearly describe what
performance looks like for that criterion at that level.
"""


def _clean_step_text(text: str) -> str:
    text = text.replace("\\n", " ").replace("\\r", " ")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^[\-\*\^#>\s]+", "", text)
    return text.strip()


def _build_ltg_prompt(schedule: list[dict]) -> str:
    week_lines = [
        f"  Week {entry.get('Week', '?')} — Skills: {entry.get('Skills', 'not specified')}"
        for entry in schedule
    ]
    return (
        "Review the uploaded curriculum materials and the weekly skills schedule below, "
        "then write a single-sentence long-term learning goal.\n\n"
        "Weekly Skills Schedule:\n" + "\n".join(week_lines)
    )


def _build_quest_name_prompt(goal_text: str, schedule: list[dict]) -> str:
    week_lines = [
        f"  Week {entry.get('Week', '?')} — Skills: {entry.get('Skills', 'not specified')}"
        for entry in schedule
    ]
    return (
        f"Long-Term Goal: {goal_text}\n\n"
        f"Weekly Skills Schedule:\n" + "\n".join(week_lines) + "\n\n"
        f"Generate exactly {len(schedule)} quest names — one per week in the order above — "
        f"that together form a coherent progression toward the long-term goal."
    )


# ---------------------------------------------------------------------------
# Main agent class
# ---------------------------------------------------------------------------


class CurriculumOnlyQuestAgent:
    """
    Generates the long-term goal and all quest details from the approved curriculum
    alone. No student profile or LTG conversation is required.

    Steps (run in order):
      1. Generate long-term goal from curriculum materials.
      2. Generate one quest name per curriculum week.
      3. Generate instructions + rubric for each quest (parallel).

    Args:
        period: Period dict — must contain ``vector_store_id``.
        schedule: List of ``{Week: int, Skills: str}`` dicts (one per curriculum week).
    """

    def __init__(self, period: dict, schedule: list[dict]) -> None:
        self.period = period
        self.schedule = schedule

        vector_store_id = period.get("vector_store_id")
        self._tools = [FileSearchTool(vector_store_ids=[vector_store_id])] if vector_store_id else []

        if not vector_store_id:
            logger.warning(
                "CurriculumOnlyQuestAgent: period %s has no vector_store_id — "
                "FileSearchTool disabled, generation will be curriculum-blind.",
                period.get("id"),
            )

    # ------------------------------------------------------------------
    # Step 1 — long-term goal
    # ------------------------------------------------------------------

    async def _generate_long_term_goal(self) -> str:
        with trace("curriculum_only_generate_ltg"):
            agent = Agent(
                name="Curriculum LTG Generator",
                instructions=_LTG_INSTRUCTIONS,
                model=CURRICULUM_ONLY_LTG_MODEL,
                output_type=LongTermGoalOutput,
                tools=self._tools,
            )
            prompt = _build_ltg_prompt(self.schedule)
            logger.debug("CurriculumOnlyQuestAgent: generating long-term goal")
            result = await Runner.run(agent, prompt)  # type: ignore[arg-type]
            output: LongTermGoalOutput = result.final_output
            logger.debug("CurriculumOnlyQuestAgent: long-term goal = %r", output.goal_text)
            return output.goal_text

    # ------------------------------------------------------------------
    # Step 2 — quest names
    # ------------------------------------------------------------------

    async def _generate_quest_names(self, goal_text: str) -> list[WeekQuest]:
        with trace("curriculum_only_generate_quest_names"):
            agent = Agent(
                name="Curriculum Quest Name Designer",
                instructions=_QUEST_NAME_INSTRUCTIONS,
                model=CURRICULUM_ONLY_QUEST_NAME_MODEL,
                output_type=QuestScheduleOutput,
                tools=self._tools,
            )
            prompt = _build_quest_name_prompt(goal_text, self.schedule)
            logger.debug(
                "CurriculumOnlyQuestAgent: generating %d quest names", len(self.schedule)
            )
            result = await Runner.run(agent, prompt)  # type: ignore[arg-type]
            output: QuestScheduleOutput = result.final_output

            if len(output.quests) != len(self.schedule):
                logger.warning(
                    "CurriculumOnlyQuestAgent: expected %d quest names, got %d — "
                    "enrichment will be partial.",
                    len(self.schedule),
                    len(output.quests),
                )
            return output.quests

    # ------------------------------------------------------------------
    # Step 3 — instructions + rubric (per quest)
    # ------------------------------------------------------------------

    async def _generate_instructions(self, quest_name: str, skills: str) -> list[dict]:
        with trace("curriculum_only_generate_instructions"):
            agent = Agent(
                name="Curriculum Instruction Generator",
                instructions=_INSTRUCTION_INSTRUCTIONS,
                model=CURRICULUM_ONLY_INSTRUCTION_MODEL,
                output_type=Instructions,
                tools=self._tools,
            )
            result = await Runner.run(  # type: ignore[arg-type]
                agent,
                f"Create detailed instructions for this quest: {quest_name} — Skills: {skills}",
            )
            steps = result.final_output.steps
            return [{"step": step.step, "text": _clean_step_text(step.text)} for step in steps]

    async def _generate_rubric(self, quest_name: str, skills: str) -> dict:
        with trace("curriculum_only_generate_rubric"):
            agent = Agent(
                name="Curriculum Rubric Generator",
                instructions=_RUBRIC_INSTRUCTIONS,
                model=CURRICULUM_ONLY_RUBRIC_MODEL,
                output_type=Rubric,
            )
            result = await Runner.run(  # type: ignore[arg-type]
                agent,
                f"Create a rubric for: {quest_name} — Skills: {skills}",
            )
            return result.final_output.to_dict_format()

    async def _process_quest(self, week_quest: WeekQuest, skills: str) -> IndividualQuest:
        with trace("curriculum_only_process_quest"):
            logger.debug("CurriculumOnlyQuestAgent: processing quest %r", week_quest.quest_name)
            instructions, rubric = await asyncio.gather(
                self._generate_instructions(week_quest.quest_name, skills),
                self._generate_rubric(week_quest.quest_name, skills),
            )
            return IndividualQuest(
                Name=week_quest.quest_name,
                Skills=skills,
                Week=week_quest.week,
                instructions=instructions,
                rubric=rubric,
            )

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    async def _run_async(self) -> tuple[str, list[IndividualQuest]]:
        with trace("curriculum_only_quest_generation"):
            logger.info(
                "CurriculumOnlyQuestAgent: starting — period %s, %d weeks",
                self.period.get("id"),
                len(self.schedule),
            )

            goal_text = await self._generate_long_term_goal()
            week_quests = await self._generate_quest_names(goal_text)

            skills_by_week: dict[int, str] = {
                entry.get("Week", idx + 1): entry.get("Skills", "")
                for idx, entry in enumerate(self.schedule)
            }

            tasks = [
                self._process_quest(wq, skills_by_week.get(wq.week, ""))
                for wq in week_quests
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful: list[IndividualQuest] = []
            for idx, result in enumerate(results, 1):
                if isinstance(result, Exception):
                    logger.error(
                        "CurriculumOnlyQuestAgent: error processing quest %d: %s",
                        idx,
                        result,
                        exc_info=True,
                    )
                else:
                    successful.append(result)  # type: ignore[arg-type]

            logger.info(
                "CurriculumOnlyQuestAgent: completed — %d/%d quests generated successfully",
                len(successful),
                len(week_quests),
            )
            return goal_text, successful

    def run(self) -> tuple[str, list[IndividualQuest]]:
        """
        Run the agent synchronously.

        Returns:
            (goal_text, quests) — the generated long-term goal string and the list
            of fully detailed IndividualQuest objects.
        """
        return asyncio.run(self._run_async())
