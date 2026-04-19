"""
Profile conversation service — wires the ProfileAgent into Flask.

Uses previous_response_id tracking for multi-turn stateful conversations
via the Responses API, avoiding the Conversations API entirely.
"""
import asyncio
from typing import Optional, Dict, Any

from agents import Runner

from EQ_agents.profile_agent import create_profile_agent, ProfileResponse


class ProfileConversationService:
    """
    Wraps the profile agent using previous_response_id for stateful tracking.
    """

    def __init__(self, previous_response_id: Optional[str] = None):
        self.agent = create_profile_agent()
        self.previous_response_id = previous_response_id

    async def initiate(self, student: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new profile conversation.

        Returns:
            Dict with ``response_id``, ``response``, ``profile_complete``,
            and optionally ``profile``.
        """
        first_name = student.get("first_name", "Student")
        last_name = student.get("last_name", "")
        initial_message = f"Hello, I'm {first_name} {last_name}."
        result = await Runner.run(self.agent, initial_message)

        response: ProfileResponse = result.final_output
        profile_complete, profile = self._check_profile(response)

        return {
            "response_id": result.last_response_id,
            "response": response.response,
            "profile_complete": profile_complete,
            **({"profile": profile} if profile else {}),
        }

    async def continue_conversation(self, user_message: str) -> Dict[str, Any]:
        """
        Continue an existing profile conversation.

        Returns:
            Dict with ``response_id``, ``response``, ``profile_complete``,
            and optionally ``profile``.
        """
        result = await Runner.run(
            self.agent,
            user_message,
            previous_response_id=self.previous_response_id,
        )

        response: ProfileResponse = result.final_output
        profile_complete, profile = self._check_profile(response)

        return {
            "response_id": result.last_response_id,
            "response": response.response,
            "profile_complete": profile_complete,
            **({"profile": profile} if profile else {}),
        }

    @staticmethod
    def _check_profile(response: ProfileResponse):
        p = response.profile
        if p and p.strengths and p.weaknesses and p.interests and p.learning_styles:
            return True, {
                "strength": p.strengths,
                "weakness": p.weaknesses,
                "interest": p.interests,
                "learning_style": p.learning_styles,
            }
        return False, None


# ---- Sync wrappers for Flask routes ----

def initiate_profile_conversation(
    student: Dict[str, Any],
) -> Dict[str, Any]:
    service = ProfileConversationService()
    return asyncio.run(service.initiate(student))


def continue_profile_conversation(
    previous_response_id: str,
    user_message: str,
) -> Dict[str, Any]:
    service = ProfileConversationService(previous_response_id)
    return asyncio.run(service.continue_conversation(user_message))
