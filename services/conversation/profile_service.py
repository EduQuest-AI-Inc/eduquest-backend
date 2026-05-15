"""
Profile conversation service — wires the ProfileAgent into Flask.

Uses previous_response_id tracking for multi-turn stateful conversations
via the Responses API, avoiding the Conversations API entirely.
"""
import asyncio
from typing import Optional, Dict, Any

from bots.protocol import BotProviderProtocol


class ProfileConversationService:
    """
    Wraps the profile agent using previous_response_id for stateful tracking.
    """

    def __init__(self, previous_response_id: Optional[str] = None, *, bot_provider: BotProviderProtocol) -> None:
        self._bot_provider = bot_provider
        self.agent = bot_provider.create_profile_agent()
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
        result = await self._bot_provider.run_conversation(
            self.agent,
            initial_message,
            trace_workflow_name="profile_conversation",
            trace_group_id=student.get("user_id"),
            trace_metadata={
                "conversation_type": "profile",
                "phase": "initiate",
                "has_student_name": bool(first_name or last_name),
                "has_previous_response_id": False,
            },
        )

        response = result.final_output
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
        result = await self._bot_provider.run_conversation(
            self.agent,
            user_message,
            previous_response_id=self.previous_response_id,
            trace_workflow_name="profile_conversation",
            trace_group_id=self.previous_response_id,
            trace_metadata={
                "conversation_type": "profile",
                "phase": "continue",
                "has_previous_response_id": bool(self.previous_response_id),
            },
        )

        response = result.final_output
        profile_complete, profile = self._check_profile(response)

        return {
            "response_id": result.last_response_id,
            "response": response.response,
            "profile_complete": profile_complete,
            **({"profile": profile} if profile else {}),
        }

    @staticmethod
    def _check_profile(response):
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
    *,
    bot_provider: BotProviderProtocol,
) -> Dict[str, Any]:
    service = ProfileConversationService(bot_provider=bot_provider)
    return asyncio.run(service.initiate(student))


def continue_profile_conversation(
    previous_response_id: str,
    user_message: str,
    *,
    bot_provider: BotProviderProtocol,
) -> Dict[str, Any]:
    service = ProfileConversationService(previous_response_id, bot_provider=bot_provider)
    return asyncio.run(service.continue_conversation(user_message))
