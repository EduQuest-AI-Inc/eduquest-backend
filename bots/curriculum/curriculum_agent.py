import logging
import sys
import os
import time
from typing import Optional
import math
from datetime import date, timedelta
from openai.types.shared import Reasoning
from pydantic import BaseModel, Field
from typing import List
from agents import Agent, Runner, FileSearchTool, trace, ModelSettings
import asyncio

logger = logging.getLogger(__name__)

# Add the parent directory to Python path so we can import from eduquest-backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ── Output schema (normalized hierarchy) ────────────────────────────────────

class SkillSchema(BaseModel):
    title: str = Field(description="Short, unique skill name")
    description: str = Field(description="What this skill means in practice")
    bloom_level: str = Field(description="One of: Remember, Understand, Apply, Analyze, Evaluate, Create")
    difficulty: str = Field(description="One of: beginner, intermediate, advanced")
    mastery_threshold: float = Field(description="Score threshold from 0.0 to 1.0")


class ConceptSchema(BaseModel):
    title: str
    description: str
    prerequisites: List[str] = Field(description="Names of other concepts that must be learned first")
    common_misconceptions: List[str]
    key_takeaways: List[str]
    skills: List[SkillSchema] = Field(description="3-5 skills associated with this concept")


class LessonSchema(BaseModel):
    title: str
    concepts: List[ConceptSchema] = Field(description="2-4 concepts covered in this lesson")


class WeekSchema(BaseModel):
    week_number: int
    start_date: str
    end_date: str
    lessons: List[LessonSchema] = Field(description="2-5 lessons per week")


class CurriculumScheduleSchema(BaseModel):
    """Schema for the full curriculum schedule output."""
    weeks: List[WeekSchema]


class CurriculumAgent:
    """
    Agent that generates a period-level semester schedule.
    This is teacher/period scoped (not student-specific).
    """

    def __init__(
        self,
        vector_store_ids: list,
        course_name: str = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        course_description: Optional[str] = None,
        grade_level: Optional[str] = None,
        research_context: Optional[str] = None,
    ) -> None:
        self.vector_store_ids = vector_store_ids or []
        self.course_description = course_description
        self.course_name = course_name or "the course"
        self.grade_level = grade_level
        self.research_context = research_context

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

        # Mode selection
        if self.vector_store_ids:
            instructions = self._files_instructions(num_weeks, calendar_section, grade_level)
        elif self.research_context:
            instructions = self._research_instructions(num_weeks, calendar_section, grade_level)
        else:
            instructions = self._description_instructions(num_weeks, calendar_section, grade_level)

        tools = (
            [FileSearchTool(vector_store_ids=self.vector_store_ids)]
            if self.vector_store_ids
            else []
        )
        self.agent = Agent(
            name="Period Schedule Agent",
            instructions=instructions,
            model="gpt-5.5",
            model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
            tools=tools,  # type: ignore[arg-type]
            output_type=CurriculumScheduleSchema
        )
        self._num_weeks = num_weeks

    # ── Mode A: uploaded files → search the vector store ────────────────────────

    @staticmethod
    def _files_instructions(num_weeks: int, calendar_section: str, grade_level: Optional[str]) -> str:
        return f"""\
You are "Weekly Course Schedule Architect," an AI agent that builds a week-by-week instructional schedule from uploaded course materials.

MISSION
Transform course materials into a fully structured weekly schedule using this hierarchy:
  Week → Lessons → Concepts → Skills

Each week must have 2-5 lessons. Each lesson must have 2-5 concepts. Each concept must have 2-5 skills.

Your output must be accurate to the provided materials and must not invent content not present in the inputs.

COURSE CONTEXT
- Grade level: {grade_level or "Not specified"}
Tailor lesson depth, vocabulary, and skill complexity to this grade level.

OPERATING PRINCIPLES
1) Evidence-first: Prefer explicit evidence from the uploaded course materials.
2) Weekly clarity: Each week must have a coherent theme, manageable lessons, and skills stated as observable outcomes.
3) Prefer materials, but fill gaps: Ground content in the materials whenever possible. If the materials are sparse for a given week, supplement with standard subject-area content appropriate for the grade level — never produce placeholder text like "Review/Catch-up," "Awaiting curriculum," or "TBD."
4) The schedule must have EXACTLY {num_weeks} weeks — no more, no fewer.
5) Never request more information from the user. Always produce a complete schedule from whatever is provided. Do not refuse, ask clarifying questions, or note that more input is needed — produce your best schedule using only the available context.

TERM CALENDAR
{calendar_section}

SCHEMA REQUIREMENTS
For each skill, provide:
- title: short, unique skill name
- description: what this skill means in practice
- bloom_level: exactly one of: Remember, Understand, Apply, Analyze, Evaluate, Create
- difficulty: exactly one of: beginner, intermediate, advanced
- mastery_threshold: float from 0.0 to 1.0

For each concept, provide:
- title, description
- prerequisites: list of other concept names that must come first (empty list if none)
- common_misconceptions: list of strings
- key_takeaways: list of strings
- skills: 3-5 SkillSchema objects

PROCESS
1. Search the course materials to understand the curriculum structure.
2. Identify modules, units, assignments, and their sequence.
3. Allocate content across exactly {num_weeks} weeks based on module order.
4. For each week, create 2-5 lessons. For each lesson, create 2-4 concepts. For each concept, create 3-5 skills.
5. Ensure every major module appears in some week. Fill any sparse weeks with grade-appropriate review or extension lessons that fit the course's logical progression."""

    # ── Mode B: no files → build from course description alone ──────────────────

    @staticmethod
    def _description_instructions(num_weeks: int, calendar_section: str, grade_level: Optional[str]) -> str:
        return f"""\
You are "Weekly Course Schedule Architect," an AI agent that builds a week-by-week instructional schedule from a teacher-provided course description.

MISSION
Build a complete, specific weekly schedule using this hierarchy:
  Week → Lessons → Concepts → Skills

Each week must have 2-5 lessons. Each lesson must have 2-4 concepts. Each concept must have 3-5 skills.

COURSE CONTEXT
- Grade level: {grade_level or "Not specified"}
Tailor lesson depth, vocabulary, and skill complexity to this grade level.

OPERATING PRINCIPLES
1) Description-driven: The course description IS the curriculum. Extract topics, units, and progression from it.
2) Infer a logical sequence: if the description names broad topics, expand them into a coherent weekly arc with specific lesson titles. If the description is thin, supplement with standard subject-area content appropriate for the grade level.
3) Every week must have real, specific lesson content — never write placeholder text like "Awaiting curriculum," "Review/Catch-up," or "Hold for materials."
4) Skills must be concrete and measurable (e.g. "Analyze causes of WWI" not "Understand history").
5) The schedule must have EXACTLY {num_weeks} weeks — no more, no fewer.
6) Never request more information from the user. Always produce a complete schedule from whatever is provided. Do not refuse, ask clarifying questions, or note that more input is needed — produce your best schedule using only the available context.

TERM CALENDAR
{calendar_section}

SCHEMA REQUIREMENTS
For each skill, provide:
- title: short, unique skill name
- description: what this skill means in practice
- bloom_level: exactly one of: Remember, Understand, Apply, Analyze, Evaluate, Create
- difficulty: exactly one of: beginner, intermediate, advanced
- mastery_threshold: float from 0.0 to 1.0

For each concept, provide:
- title, description
- prerequisites: list of other concept names that must come first (empty list if none)
- common_misconceptions: list of strings
- key_takeaways: list of strings
- skills: 3-5 SkillSchema objects

PROCESS
1. Read the course description to identify the subject, major topics, and any stated goals or units.
2. Divide the topics into a logical instructional sequence across {num_weeks} weeks.
3. For each week, create 2-5 lessons with specific titles a teacher would actually use.
4. For each lesson, create 2-4 concepts with full metadata.
5. For each concept, derive 3-5 measurable skills with bloom_level and difficulty."""

    # ── Mode C: description + Perplexity research context ───────────────────────

    @staticmethod
    def _research_instructions(num_weeks: int, calendar_section: str, grade_level: Optional[str]) -> str:
        return f"""\
You are "Weekly Course Schedule Architect," an AI agent that builds a week-by-week instructional schedule from a teacher-provided course description supplemented by web research.

MISSION
Build a complete, specific, research-informed weekly schedule using this hierarchy:
  Week → Lessons → Concepts → Skills

Each week must have 2-5 lessons. Each lesson must have 2-4 concepts. Each concept must have 3-5 skills.

COURSE CONTEXT
- Grade level: {grade_level or "Not specified"}
Tailor lesson depth, vocabulary, and skill complexity to this grade level.

OPERATING PRINCIPLES
1) Description-first: The teacher's course description defines the overall curriculum intent.
2) Research-informed: The RESEARCH CONTEXT (provided in the user prompt) fills in curriculum gaps with authoritative, web-sourced content. Use it to produce rich, accurate concept definitions, misconceptions, and skills.
3) Every week must have real, specific lesson content — never write placeholder text.
4) Skills must be concrete and measurable (e.g. "Solve linear equations using substitution" not "Understand algebra").
5) The schedule must have EXACTLY {num_weeks} weeks — no more, no fewer.
6) Never request more information from the user. Always produce a complete schedule from whatever is provided. Do not refuse, ask clarifying questions, or note that more input is needed — produce your best schedule using only the available context.

TERM CALENDAR
{calendar_section}

SCHEMA REQUIREMENTS
For each skill, provide:
- title: short, unique skill name
- description: what this skill means in practice
- bloom_level: exactly one of: Remember, Understand, Apply, Analyze, Evaluate, Create
- difficulty: exactly one of: beginner, intermediate, advanced
- mastery_threshold: float from 0.0 to 1.0

For each concept, provide:
- title, description
- prerequisites: list of other concept names that must come first (empty list if none)
- common_misconceptions: list of strings (draw from the research context where relevant)
- key_takeaways: list of strings
- skills: 3-5 SkillSchema objects

PROCESS
1. Read the course description to identify the subject, major topics, and goals.
2. Consult the RESEARCH CONTEXT to enrich concepts with accurate terminology, common misconceptions, and learning progressions.
3. Divide the topics into a logical instructional sequence across {num_weeks} weeks.
4. For each week, create 2-5 lessons with specific titles a teacher would actually use.
5. For each lesson, create 2-4 concepts with full metadata informed by the research.
6. For each concept, derive 3-5 measurable skills with bloom_level and difficulty."""

    async def _run_async(self) -> CurriculumScheduleSchema:
        mode = "files" if self.vector_store_ids else ("research" if self.research_context else "description")
        logger.info(
            "CurriculumAgent starting: course=%r mode=%s weeks=%d model=gpt-5.5",
            self.course_name, mode, self._num_weeks,
        )
        t0 = time.monotonic()
        grade_line = f"Grade level: {self.grade_level or 'Not specified'}"

        if self.vector_store_ids:
            base_prompt = f"""Please create a weekly semester schedule for {self.course_name} based on the course materials in the vector store.

{grade_line}

Search the course materials to understand:
- What modules/units exist
- What topics are covered
- Any assignments, quizzes, or due dates
- The sequence and structure of the curriculum

Then produce a complete weekly schedule covering the entire semester."""
        else:
            base_prompt = f"""Please create a weekly semester schedule for {self.course_name}.

{grade_line}

No course files were uploaded. Use the following teacher-provided description as your primary curriculum source:

{self.course_description}"""

        if self.research_context:
            prompt = f"""{base_prompt}

RESEARCH CONTEXT (gathered from Perplexity Sonar — use this to fill curriculum gaps):
{self.research_context}
"""
        else:
            prompt = base_prompt

        with trace("curriculum_generation"):
            result = await Runner.run(
                self.agent,
                prompt
            )

        elapsed = time.monotonic() - t0
        logger.info("CurriculumAgent complete: elapsed=%.1fs", elapsed)
        return result.final_output

    def run(self) -> CurriculumScheduleSchema:
        """Run the agent synchronously and return the schedule."""
        return asyncio.run(self._run_async())

    async def run_async(self) -> CurriculumScheduleSchema:
        """Run the agent asynchronously and return the schedule."""
        return await self._run_async()

    def run_and_get_json(self) -> dict:
        """Run the agent and return the schedule as a JSON-serializable dict."""
        schedule = self.run()
        return schedule.model_dump()

    async def run_and_get_json_async(self) -> dict:
        """Run the agent asynchronously and return the schedule as a JSON-serializable dict."""
        schedule = await self.run_async()
        return schedule.model_dump()
