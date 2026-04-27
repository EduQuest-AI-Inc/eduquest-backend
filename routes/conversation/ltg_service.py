"""
LTG conversation service — wires the LTG agent into Flask.

Uses previous_response_id tracking for multi-turn stateful conversations
via the Responses API, avoiding the Conversations API entirely.
"""
import asyncio
from typing import Optional, Dict, Any

from agents import Runner

from bots.ltg_agent import create_ltg_agent, LTGResponse


class LTGConversationService:
    """
    Persistent LTG conversation using previous_response_id tracking.

    Each student has one last_response_id per class (period), persisted
    in the ltg_conversation table.
    """

    def __init__(self, vector_store_id: str, previous_response_id: Optional[str] = None) -> None:
        self.vector_store_id = vector_store_id
        self.previous_response_id = previous_response_id
        self.agent = create_ltg_agent(vector_store_id)

    async def initiate(self, student: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new LTG conversation for a student."""
        first_name = student.get("first_name", "Student")
        last_name = student.get("last_name", "")
        grade = student.get("grade", "")

        strengths = self._format_list_field(student.get("strength", []))
        weaknesses = self._format_list_field(student.get("weakness", []))
        interests = self._format_list_field(student.get("interest", []))
        learning_style = self._format_list_field(student.get("learning_style", []))

        initial_message = (
            f"Hello, I'm {first_name} {last_name}"
            f"{', in ' + str(grade) + 'th grade' if grade else ''}. "
            f"My strengths are {strengths}, my weaknesses are {weaknesses}, "
            f"my interests are {interests}, and my learning style is {learning_style}. "
            f"Please search the course materials and recommend 3 long-term goals for me "
            f"that incorporate what I'll learn in this class."
        )

        result = await Runner.run(self.agent, initial_message)

        response: LTGResponse = result.final_output

        return {
            "response_id": result.last_response_id,
            "message": response.message,
            "goal_1": response.goal_1,
            "goal_2": response.goal_2,
            "goal_3": response.goal_3,
            "chosen_goal": response.chosen_goal,
        }

    async def continue_conversation(self, user_message: str) -> Dict[str, Any]:
        """Continue an existing LTG conversation."""
        result = await Runner.run(
            self.agent,
            user_message,
            previous_response_id=self.previous_response_id,
        )

        response: LTGResponse = result.final_output
        goal_chosen = bool(
            response.chosen_goal
            and response.chosen_goal.lower() not in ("null", "none", "")
        )

        return {
            "response_id": result.last_response_id,
            "message": response.message if not goal_chosen else response.chosen_goal,
            "chosen_goal": response.chosen_goal if goal_chosen else None,
            "goal_chosen": goal_chosen,
        }

    @staticmethod
    def _format_list_field(field) -> str:
        if isinstance(field, list):
            return ", ".join(str(item) for item in field) if field else "not specified"
        return str(field) if field else "not specified"


# ---- Sync wrappers for Flask routes ----

def initiate_ltg_conversation(
    vector_store_id: str,
    student: Dict[str, Any],
    previous_response_id: Optional[str] = None,
) -> Dict[str, Any]:
    service = LTGConversationService(vector_store_id, previous_response_id)
    return asyncio.run(service.initiate(student))


def continue_ltg_conversation(
    vector_store_id: str,
    previous_response_id: str,
    user_message: str,
) -> Dict[str, Any]:
    service = LTGConversationService(vector_store_id, previous_response_id)
    return asyncio.run(service.continue_conversation(user_message))
