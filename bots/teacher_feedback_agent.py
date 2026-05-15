"""
Teacher Feedback Agent — OpenAI Agents SDK.

Handles conversations between teachers and the AI about student progress.
Helps teachers provide feedback and suggests changes to student profiles or quests.
"""
from typing import Optional
from pydantic import BaseModel, Field

from agents import Agent
from bots.model_config import TEACHER_FEEDBACK_MODEL


# --- Pydantic schemas ---

class TeacherFeedbackResponse(BaseModel):
    response: str = Field(description="Response to the teacher")
    suggested_change: Optional[str] = Field(
        default=None,
        description="Suggested change to student profile or quests",
    )


# --- Agent factory ---

def create_teacher_feedback_agent() -> Agent:
    """
    Create a teacher feedback agent.

    Returns:
        Configured Agent instance (no student guardrails — teacher-facing).
    """
    instructions = """You are an educational assistant that helps teachers provide feedback about students.

Your role:
1. Ask the teacher what they've noticed about the student
2. Discuss what changes they'd like to make to the student's profile or future quests
3. Help update student profiles based on teacher observations
4. Suggest quest modifications based on teacher feedback

When you have enough information to suggest a specific change, include it in the suggested_change field.
Otherwise, leave suggested_change as null and continue the conversation.

Keep conversations collaborative and focused on student improvement.
Ask specific questions to gather actionable insights."""

    return Agent(
        name="Teacher Feedback Agent",
        instructions=instructions,
        model=TEACHER_FEEDBACK_MODEL,
        output_type=TeacherFeedbackResponse,
    )
