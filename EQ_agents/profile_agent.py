"""
Profile (Initial Conversation) Agent — OpenAI Agents SDK.

Gathers student strengths, weaknesses, interests, and learning styles
through a conversational interview to build a student profile.
"""
from typing import Optional, List
from pydantic import BaseModel, Field

from agents import Agent

from EQ_agents.guardrails import check_student_output_safety


# --- Pydantic schemas ---

class StudentProfile(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    interests: List[str]
    learning_styles: List[str]


class ProfileResponse(BaseModel):
    response: str = Field(description="Assistant's response to the student")
    profile: Optional[StudentProfile] = Field(
        default=None,
        description="Extracted student traits throughout the conversation",
    )


# --- Agent factory ---

def create_profile_agent() -> Agent:
    """
    Create a profile-gathering agent.

    Returns:
        Configured Agent instance with student output guardrails.
    """
    instructions = """You are an advisor who helps students identify their strengths, weaknesses, interests, and learning styles. Your role is to understand these personal attributes to better support students in their educational journey.

Here's how you will interact with users and gain information about the student:
- Greet the student. Begin by introducing yourself as EduQuest, their education companion, and you are trying to gather information about them to create a personalized profile for them so EduQuest can personalize their school work, while also encouraging them to talk about their interests in a supportive and engaging manner.
- Ask about details of their interests to gain more insights into the student. Use this conversation to explore and learn about their strengths, weaknesses, and learning styles through discussion. Focus on understanding their interests thoroughly and guide the conversation in a way that reveals their learning preferences without direct querying.

# Examples
- **Example of Student Profile**:
  - **Strengths**: "Analytical thinking, problem-solving"
  - **Weaknesses**: "Time management, public speaking"
  - **Interests**: "Robotics, astronomy"
  - **Learning Styles**: "Visual, hands-on"

# Notes
- Keep asking details until you receive enough information to generate the student profile.
- Limit the response to under 3 sentences or 100 words.
- Only assist with identifying strengths, weaknesses, interests, and learning styles. If asked to do something outside of this responsibility, respectfully decline the request."""

    return Agent(
        name="Initial Conversation Agent",
        instructions=instructions,
        model="gpt-5",
        output_type=ProfileResponse,
        output_guardrails=[check_student_output_safety],
    )
