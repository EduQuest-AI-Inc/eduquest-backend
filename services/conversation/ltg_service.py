"""
LTG conversation service — wires the LTG agent into FastAPI.

Uses previous_response_id tracking for multi-turn stateful conversations
via the Responses API, avoiding the Conversations API entirely.
"""
import asyncio
import uuid
from typing import Optional, Dict, Any

from bots.protocol import BotProviderProtocol
from data_access.ltg_conversation_dao import LtgConversationDAO
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError
from services.curriculum.curriculum_service import CurriculumService


class LTGConversationService:
    """
    Persistent LTG conversation using previous_response_id tracking.

    Each student has one last_response_id per class (period), persisted
    in the ltg_conversation table.
    """

    def __init__(self, vector_store_id: str, curriculum: dict, previous_response_id: Optional[str] = None, *, bot_provider: BotProviderProtocol) -> None:
        self._bot_provider = bot_provider
        self.vector_store_id = vector_store_id
        self.has_curriculum = bool(curriculum)
        self.previous_response_id = previous_response_id
        self.agent = bot_provider.create_ltg_agent(vector_store_id, curriculum)

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

        result = await self._bot_provider.run_conversation(
            self.agent,
            initial_message,
            trace_workflow_name="ltg_conversation",
            trace_group_id=getattr(self, "vector_store_id", None),
            trace_metadata={
                "conversation_type": "ltg",
                "phase": "initiate",
                "has_vector_store": bool(getattr(self, "vector_store_id", None)),
                "has_curriculum": bool(getattr(self, "has_curriculum", False)),
                "has_grade": bool(grade),
                "has_previous_response_id": False,
            },
        )

        response = result.final_output
        if response is None:
            raise ValidationError("LTG agent returned no structured output")

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
        result = await self._bot_provider.run_conversation(
            self.agent,
            user_message,
            previous_response_id=self.previous_response_id,
            trace_workflow_name="ltg_conversation",
            trace_group_id=self.previous_response_id or getattr(self, "vector_store_id", None),
            trace_metadata={
                "conversation_type": "ltg",
                "phase": "continue",
                "has_vector_store": bool(getattr(self, "vector_store_id", None)),
                "has_curriculum": bool(getattr(self, "has_curriculum", False)),
                "has_previous_response_id": bool(self.previous_response_id),
            },
        )

        response = result.final_output
        if response is None:
            raise ValidationError("LTG agent returned no structured output")
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


# ---- Full orchestration (validation + DAO + AI) ----

class LTGOrchestrationService:

    def __init__(
        self,
        period_dao=None,
        student_dao=None,
        ltg_conversation_dao=None,
        student_long_term_goal_dao=None,
        curriculum_service=None,
        *,
        bot_provider: BotProviderProtocol,
        jwt: str | None = None,
    ) -> None:
        self._bot_provider = bot_provider
        self.period_dao = period_dao or PeriodDAO(jwt=jwt)
        self.student_dao = student_dao or StudentDAO(jwt=jwt)
        # ltg_conversation and student_long_term_goal are INSERT/UPDATE/DELETE FastAPI-only;
        # admin client required for all mutations (and reads are safe via admin too)
        self.ltg_conversation_dao = ltg_conversation_dao or LtgConversationDAO()
        self.student_long_term_goal_dao = student_long_term_goal_dao or StudentLongTermGoalDAO()
        self.curriculum_service = curriculum_service or CurriculumService(bot_provider=bot_provider, jwt=jwt)

    async def initiate(self, user_id: str, period_id: str) -> Dict[str, Any]:
        if not period_id:
            raise ValidationError("Missing period ID")

        student = await asyncio.to_thread(self.student_dao.get_student_by_id, user_id)
        if not student:
            raise NotFoundError("Student not found")

        period = await asyncio.to_thread(self.period_dao.get_period_by_id, period_id)
        if not period:
            raise NotFoundError("Invalid period ID")

        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise ValidationError("Period does not have a vector store configured")

        existing_conversation_id = await asyncio.to_thread(
            self.ltg_conversation_dao.get_conversation_id, user_id, period_id
        )
        if existing_conversation_id:
            return {
                "conversation_id": existing_conversation_id,
                "response": {"message": "Welcome back! Let's continue working on your long-term goal."},
                "resumed": True,
            }

        curriculum = await asyncio.to_thread(self.curriculum_service.get_curriculum, period_id)

        student_data = {
            "first_name": student.get("first_name", ""),
            "last_name": student.get("last_name", ""),
            "grade": student.get("grade", ""),
            "strength": student.get("strength", []),
            "weakness": student.get("weakness", []),
            "interest": student.get("interest", []),
            "learning_style": student.get("learning_style", []),
        }

        service = LTGConversationService(vector_store_id, curriculum, bot_provider=self._bot_provider)
        result = await service.initiate(student_data)

        response_id = result.get("response_id")
        if not response_id:
            raise ValidationError("LTG agent did not return a response_id")

        conversation_id = str(uuid.uuid4())
        await asyncio.to_thread(
            self.ltg_conversation_dao.upsert_conversation,
            user_id, period_id, conversation_id, last_response_id=response_id,
        )

        return {
            "conversation_id": conversation_id,
            "response": {
                "message": result.get("message", ""),
                "goal_1": result.get("goal_1"),
                "goal_2": result.get("goal_2"),
                "goal_3": result.get("goal_3"),
            },
            "resumed": False,
        }

    async def continue_conversation(
        self,
        user_id: str,
        conversation_type: str,
        conversation_id: str,
        message: str,
        period_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not period_id:
            period_id = await asyncio.to_thread(
                self.ltg_conversation_dao.find_period_for_conversation, user_id, conversation_id
            )
        if not period_id:
            raise NotFoundError("Could not determine period for conversation")

        period = await asyncio.to_thread(self.period_dao.get_period_by_id, period_id)
        if not period:
            raise NotFoundError("Period not found")

        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise ValidationError("Period does not have a vector store configured")

        last_response_id = await asyncio.to_thread(
            self.ltg_conversation_dao.get_last_response_id, user_id, period_id
        )

        service = LTGConversationService(vector_store_id, {}, last_response_id, bot_provider=self._bot_provider)
        result = await service.continue_conversation(message)

        new_response_id = result.get("response_id")
        if new_response_id:
            await asyncio.to_thread(
                self.ltg_conversation_dao.update_last_response_id, user_id, period_id, new_response_id
            )

        reply = result.get("message", "")
        goal_chosen = result.get("goal_chosen", False)
        chosen_goal = result.get("chosen_goal")

        if goal_chosen and chosen_goal:
            await asyncio.to_thread(self.student_long_term_goal_dao.upsert, user_id, period_id, chosen_goal)

        return {"response": reply, "goal_chosen": goal_chosen}
