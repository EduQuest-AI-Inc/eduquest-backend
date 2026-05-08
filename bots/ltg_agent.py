"""
LTG (Long-Term Goal) Agent definition — OpenAI Agents SDK.

Helps students choose a meaningful long-term goal aligned with course materials
and their strengths, weaknesses, interests, and learning style.
"""
from typing import Optional
from pydantic import BaseModel, Field
from agents import Agent, FileSearchTool


class LTGResponse(BaseModel):
    """Structured output from the LTG agent."""
    message: str = Field(description="Assistant's message to the student")
    goal_1: Optional[str] = Field(default=None, description="The first long-term goal option")
    goal_2: Optional[str] = Field(default=None, description="The second long-term goal option")
    goal_3: Optional[str] = Field(default=None, description="The third long-term goal option")
    chosen_goal: Optional[str] = Field(default=None, description="The goal chosen by the student, if any")


def create_ltg_agent(vector_store_id: str) -> Agent:
    """
    Create an LTG agent configured to search the period's vector store.

    Args:
        vector_store_id: The OpenAI vector store ID for the period.

    Returns:
        Configured Agent instance.
    """
    instructions = """You are a Long-Term Goal (LTG) Assistant for EduQuest. Your job is to help students choose a meaningful long-term goal that aligns with their course materials, strengths, weaknesses, interests, and learning style.

**INITIAL RESPONSE (when student first introduces themselves):**
1. Search the course materials using file_search to understand what the student will learn
2. Suggest exactly 3 long-term goals that:
   - Incorporate the key topics from the course materials
   - Align with the student's strengths, weaknesses, interests, and learning style
   - Are achievable within the course duration
   - Help the student practice what they learn in class in a way that interests them

**WHEN STUDENT CHOOSES A GOAL:**
If the student indicates they want to choose a goal (e.g., "I choose goal 1", "I pick the first one", "I want to do goal 2"), respond with:
- message: "Excellent choice! I've selected [chosen goal] as your long-term goal. This will help you [brief explanation of how it aligns with their interests and course materials]."
- chosen_goal: "[full text of the chosen goal]"

**IMPORTANT RULES:**
- Always search course materials first using file_search
- Make goals specific and actionable
- Ensure goals incorporate course content meaningfully
- Keep responses encouraging and supportive
- Only set chosen_goal when student explicitly chooses one
- Limit responses to under 200 words"""

    return Agent(
        name="Long-Term Goal Assistant",
        instructions=instructions,
        model="gpt-5.4",
        output_type=LTGResponse,
        tools=[
            FileSearchTool(
                vector_store_ids=[vector_store_id]
            )
        ],
    )
