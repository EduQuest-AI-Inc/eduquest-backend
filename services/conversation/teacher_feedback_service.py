"""
Teacher feedback service — wires the TeacherFeedbackAgent into Flask.

Uses OpenAIConversationsSession so teachers can have a multi-turn
conversation about student progress.  Replaces the teacher-facing branch
of the legacy ``update`` class from assistants.py.
"""
import asyncio
from typing import Optional, Dict, Any

from bots.provider import get_bot_provider


class TeacherFeedbackConversationService:
    """
    Persistent, multi-turn teacher-feedback conversation backed by an
    OpenAI Conversations session.
    """

    def __init__(self, conversation_id: Optional[str] = None) -> None:
        self.agent = get_bot_provider().create_teacher_feedback_agent()
        self.session = get_bot_provider().make_conversations_session(conversation_id)

    async def _extract_conversation_id(self) -> Optional[str]:
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

    async def initiate(
        self,
        student: Dict[str, Any],
        quests_summary: str,
    ) -> Dict[str, Any]:
        """
        Start a teacher-feedback conversation.

        Args:
            student: Student data dict.
            quests_summary: JSON or text summary of the student's quests.

        Returns:
            Dict with ``conversation_id``, ``response``, ``suggested_change``.
        """
        student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
        initial_message = (
            f"I'm a teacher reviewing student {student_name}.\n"
            f"Here is their quest data:\n{quests_summary}\n"
            f"What have you noticed about this student?"
        )

        result = await get_bot_provider().run_conversation(
            self.agent,
            initial_message,
            session=self.session,
        )

        response = result.final_output
        conversation_id = await self._extract_conversation_id()

        return {
            "conversation_id": conversation_id,
            "response": response.response,
            "suggested_change": response.suggested_change,
        }

    async def continue_conversation(self, user_message: str) -> Dict[str, Any]:
        """Continue an existing teacher-feedback conversation."""
        result = await get_bot_provider().run_conversation(
            self.agent,
            user_message,
            session=self.session,
        )

        response = result.final_output

        return {
            "response": response.response,
            "suggested_change": response.suggested_change,
        }


# ---- Sync wrappers for Flask routes ----

def initiate_teacher_feedback(
    student: Dict[str, Any],
    quests_summary: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    service = TeacherFeedbackConversationService(conversation_id)
    return asyncio.run(service.initiate(student, quests_summary))


def continue_teacher_feedback(
    conversation_id: str,
    user_message: str,
) -> Dict[str, Any]:
    service = TeacherFeedbackConversationService(conversation_id)
    return asyncio.run(service.continue_conversation(user_message))
