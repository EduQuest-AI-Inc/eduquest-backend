"""
Multi-Agent Grading Orchestrator — OpenAI Agents SDK.

Grades student quest submissions using 4 specialized sub-agents:
  1. Numerical Grading Agent — assigns rubric-based scores
  2. Feedback Generation Agent — writes constructive feedback
  3. Skill Mastery Assessment Agent — evaluates skill demonstration
  4. Homework Adaptation Agent — recommends curriculum changes

The orchestrator runs them sequentially, piping outputs forward.
"""
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from agents import Agent, Runner, AgentOutputSchema

from bots.guardrails import check_student_output_safety


# --- Pydantic schemas ---

class GradingInput(BaseModel):
    submission: str = Field(description="The student's submission")
    rubric: Dict[str, Any] = Field(description="The grading rubric")
    skills: List[str] = Field(description="Skills being assessed")
    instructions: str = Field(description="Assignment instructions")


class NumericalGrade(BaseModel):
    criteria_scores: Dict[str, int] = Field(description="Score for each rubric criterion")
    total_score: int = Field(description="Total numerical score")
    max_possible: int = Field(description="Maximum possible points")


class StudentFeedback(BaseModel):
    feedback: str = Field(description="Constructive feedback for the student")


class SkillMastery(BaseModel):
    skill_mastery: Dict[str, float] = Field(description="Skill mastery levels (0.0-1.0)")


class HomeworkRecommendation(BaseModel):
    changes_recommended: bool = Field(description="Whether changes are recommended")
    recommended_changes: Optional[List[str]] = Field(description="Specific change recommendations")


class GradingResult(BaseModel):
    numerical_grade: int = Field(description="Total points from rubric")
    feedback: str = Field(description="Student-facing feedback")
    skill_mastery: Dict[str, float] = Field(description="Skill to mastery level mapping")
    homework_changes_recommended: bool = Field(description="Whether homework changes are recommended")
    recommended_changes: Optional[List[str]] = Field(description="Specific change suggestions")


# --- Orchestrator ---

class GradingOrchestrator:
    """
    Multi-agent grading system that coordinates 4 specialized sub-agents
    to produce a comprehensive grading result.
    """

    def __init__(self) -> None:
        self.numerical_agent = Agent(
            name="Numerical Grading Agent",
            instructions="""You are a numerical grading specialist. Analyze the student submission against the provided rubric.

            For each criterion in the rubric:
            1. Evaluate the submission's performance on that criterion
            2. Assign a numerical score based on the rubric scale
            3. Be fair but rigorous in your assessment

            Calculate the total score and maximum possible points.""",
            model="gpt-5",
            output_type=AgentOutputSchema(NumericalGrade, strict_json_schema=False),
        )

        self.feedback_agent = Agent(
            name="Feedback Generation Agent",
            instructions="""You are a feedback specialist focused on student growth. Based on the numerical scores and submission:

            1. Provide constructive, encouraging feedback
            2. Highlight specific strengths in the work
            3. Identify areas for improvement with actionable suggestions
            4. Maintain a supportive, educational tone
            5. Reference specific parts of the submission

            Your feedback should help the student understand their performance and how to improve.""",
            model="gpt-5",
            output_type=AgentOutputSchema(StudentFeedback, strict_json_schema=False),
            output_guardrails=[check_student_output_safety],
        )

        self.mastery_agent = Agent(
            name="Skill Mastery Assessment Agent",
            instructions="""You are a skill assessment specialist. Analyze the student's demonstration of target skills.

            For each skill:
            1. Evaluate evidence of mastery in the submission (0.0 = no evidence, 1.0 = full mastery)
            2. Consider the quality and depth of skill demonstration
            3. Be objective and evidence-based in your assessment

            Focus on what the student has actually demonstrated, not potential or effort.""",
            model="gpt-5",
            output_type=AgentOutputSchema(SkillMastery, strict_json_schema=False),
        )

        self.adaptation_agent = Agent(
            name="Homework Adaptation Agent",
            instructions="""You are a curriculum adaptation specialist. Based on skill gaps and performance patterns:

            1. Determine if homework changes are needed (threshold: skill mastery < 0.7 or total score < 70%)
            2. If changes needed, recommend specific adaptations:
               - Difficulty adjustments (easier/harder)
               - Additional practice areas
               - Different learning approaches
               - Prerequisite skill reinforcement

            Only recommend changes when there's clear evidence of need.""",
            model="gpt-5",
            output_type=AgentOutputSchema(HomeworkRecommendation, strict_json_schema=False),
        )

    async def grade_submission(self, grading_input: GradingInput) -> GradingResult:
        """Orchestrate the full grading process using multiple specialized agents."""

        # Step 1: Numerical grading
        numerical_result = await Runner.run(
            self.numerical_agent,
            f"""Grade this submission:

            Instructions: {grading_input.instructions}
            Rubric: {json.dumps(grading_input.rubric, indent=2)}
            Submission: {grading_input.submission}""",
        )
        numerical_grade = numerical_result.final_output

        # Step 2: Generate feedback based on numerical results
        feedback_result = await Runner.run(
            self.feedback_agent,
            f"""Generate feedback for this submission:

            Submission: {grading_input.submission}
            Scores: {numerical_grade.criteria_scores}
            Total Score: {numerical_grade.total_score}/{numerical_grade.max_possible}
            Rubric: {json.dumps(grading_input.rubric, indent=2)}""",
        )
        student_feedback = feedback_result.final_output

        # Step 3: Assess skill mastery
        mastery_result = await Runner.run(
            self.mastery_agent,
            f"""Assess skill mastery for:

            Target Skills: {grading_input.skills}
            Submission: {grading_input.submission}
            Performance Score: {numerical_grade.total_score}/{numerical_grade.max_possible}""",
        )
        skill_mastery = mastery_result.final_output

        # Step 4: Determine homework adaptations
        adaptation_result = await Runner.run(
            self.adaptation_agent,
            f"""Analyze need for homework changes:

            Skill Mastery: {skill_mastery.skill_mastery}
            Total Score: {numerical_grade.total_score}/{numerical_grade.max_possible}
            Performance: {numerical_grade.criteria_scores}""",
        )
        homework_rec = adaptation_result.final_output

        # Combine results
        return GradingResult(
            numerical_grade=numerical_grade.total_score,
            feedback=student_feedback.feedback,
            skill_mastery=skill_mastery.skill_mastery,
            homework_changes_recommended=homework_rec.changes_recommended,
            recommended_changes=homework_rec.recommended_changes,
        )
