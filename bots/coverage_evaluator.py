"""
Coverage Evaluator — determines whether available course materials are sufficient
to generate a rich curriculum, and produces Perplexity search queries for any gaps.

Uses a single structured OpenAI completion (no Agent overhead) for speed.
"""
import os
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel


class CoverageResult(BaseModel):
    sufficient: bool
    gaps: List[str]            # topic areas not covered by the materials
    research_queries: List[str]  # Perplexity search queries to fill the gaps


class CoverageEvaluator:
    """
    Evaluates whether a course description (and optional files) contains enough
    information to build a complete, accurate K-12 curriculum schedule.

    If not sufficient, returns research queries suitable for Perplexity Sonar.
    """

    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def evaluate(
        self,
        course_name: str,
        course_description: Optional[str],
        has_files: bool,
        grade_level: Optional[str] = None,
    ) -> CoverageResult:
        """
        Evaluate whether available materials are sufficient for schedule generation.

        Args:
            course_name: The name of the course (e.g. "AP US History").
            course_description: Teacher-provided description (may be None or thin).
            has_files: Whether the teacher has uploaded course files/syllabi.
            grade_level: Optional grade level string (e.g. "10th grade", "AP").

        Returns:
            CoverageResult with sufficient flag, gaps list, and research_queries list.
        """
        grade_context = f" for {grade_level}" if grade_level else ""
        description_text = course_description.strip() if course_description else ""
        description_block = (
            f"Course description:\n{description_text}"
            if description_text
            else "No course description provided."
        )
        files_note = (
            "The teacher has uploaded course files (syllabus, materials, etc.)."
            if has_files
            else "No course files have been uploaded."
        )

        system_prompt = """\
You are a curriculum coverage analyst. Your job is to decide whether available \
course information is sufficient to generate a complete, rich semester schedule \
(week → lesson → concept → skill hierarchy) for a K-12 or college course.

A description is "sufficient" if it clearly names major units/topics and provides \
enough detail to derive specific lessons, concepts, and measurable skills without \
guessing. An empty description, a one-sentence description, or a description that \
only names the subject area is NOT sufficient.

If uploaded course files are present, the description bar is lower — files contain \
the real curriculum detail.

Return JSON matching this schema:
{
  "sufficient": bool,
  "gaps": ["list of broad topic areas that are missing or underspecified"],
  "research_queries": ["specific Perplexity Sonar search queries to fill each gap"]
}

Research queries should be concrete enough to return curriculum-relevant results, e.g.:
  "AP US History units and topics College Board curriculum guide"
  "10th grade biology common misconceptions cell division"
Keep research_queries empty if sufficient=true."""

        user_prompt = f"""\
Course name: {course_name}{grade_context}
{files_note}

{description_block}

Evaluate whether the above information is sufficient to generate a complete \
semester schedule. Identify gaps and provide research queries if needed."""

        completion = self._client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=CoverageResult,
        )

        return completion.choices[0].message.parsed
