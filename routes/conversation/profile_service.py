"""
Profile conversation service — wires the ProfileAgent into Flask.

Uses OpenAIConversationsSession + Runner.run() for multi-turn profile
gathering.  Replaces the legacy ``ini_conv`` class from assistants.py.
"""
import asyncio
from typing import Optional, Dict, Any

from agents import Runner, OpenAIConversationsSession

from EQ_agents.profile_agent import create_profile_agent, ProfileResponse


class ProfileConversationService:
    """
    Wraps the profile agent with an OpenAI Conversations session so that
    each student has a persistent, resumable profile conversation.
    """

    def __init__(self, conversation_id: Optional[str] = None):
        self.agent = create_profile_agent()
        if conversation_id:
            self.session = OpenAIConversationsSession(conversation_id=conversation_id)
        else:
            self.session = OpenAIConversationsSession()

    async def _extract_conversation_id(self) -> Optional[str]:
        """Pull the OpenAI-assigned conversation_id out of the session."""
        try:
            getter = getattr(self.session, "_get_session_id", None)
            if callable(getter):
                sid = getter()
                if asyncio.iscoroutine(sid):
                    sid = await sid
                if isinstance(sid, str) and sid:
                    return sid
        except Exception:
            pass

        sid2 = getattr(self.session, "_session_id", None)
        if isinstance(sid2, str) and sid2:
            return sid2
        return None

    async def initiate(self, student: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new profile conversation.

        Args:
            student: Student dict with ``first_name``, ``last_name``.

        Returns:
            Dict with ``conversation_id``, ``response``, ``profile_complete``,
            and optionally ``profile``.
        """
        first_name = student.get("first_name", "Student")
        last_name = student.get("last_name", "")
        initial_message = f"Hello, I'm {first_name} {last_name}."
        result = await Runner.run(
            self.agent,
            initial_message,
            session=self.session,
        )

        response: ProfileResponse = result.final_output
        conversation_id = await self._extract_conversation_id()
        profile_complete, profile = self._check_profile(response)

        return {
            "conversation_id": conversation_id,
            "response": response.response,
            "profile_complete": profile_complete,
            **({"profile": profile} if profile else {}),
        }

    async def continue_conversation(self, user_message: str) -> Dict[str, Any]:
        """
        Continue an existing profile conversation.

        Returns:
            Dict with ``response``, ``profile_complete``, and optionally ``profile``.
        """
        result = await Runner.run(
            self.agent,
            user_message,
            session=self.session,
        )

        response: ProfileResponse = result.final_output
        profile_complete, profile = self._check_profile(response)

        return {
            "response": response.response,
            "profile_complete": profile_complete,
            **({"profile": profile} if profile else {}),
        }

    @staticmethod
    def _check_profile(response: ProfileResponse):
        """
        Return (is_complete, normalized_profile_dict | None).

        The profile is considered complete when all four trait lists are
        non-empty.  Keys are normalized to match ``StudentDAO.update_student``.
        """
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
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    service = ProfileConversationService(conversation_id)
    return asyncio.run(service.initiate(student))


def continue_profile_conversation(
    conversation_id: str,
    user_message: str,
) -> Dict[str, Any]:
    service = ProfileConversationService(conversation_id)
    return asyncio.run(service.continue_conversation(user_message))
