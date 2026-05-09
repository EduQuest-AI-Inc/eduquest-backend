"""
LTG conversation service — wires the LTG agent into Fast API.

Uses previous_response_id tracking for multi-turn stateful conversations
via the Responses API, avoiding the Conversations API entirely.
"""
import asyncio
import uuid
from typing import Optional, Dict, Any

from bots.provider import get_bot_provider
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.ltg_conversation_dao import LtgConversationDAO
from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
from services.curriculum.curriculum_service import CurriculumService
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError


class LTGConversationService:
    """
    Persistent LTG conversation using previous_response_id tracking.

    Each student has one last_response_id per class (period), persisted
    in the ltg_conversation table.
    """

    def __init__(self, vector_store_id: str, curriculum: dict, previous_response_id: Optional[str] = None) -> None:
        self.vector_store_id = vector_store_id
        self.previous_response_id = previous_response_id
        self.agent = get_bot_provider().create_ltg_agent(vector_store_id, curriculum)

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

        result = await get_bot_provider().run_conversation(self.agent, initial_message)

        response = result.final_output

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
        result = await get_bot_provider().run_conversation(
            self.agent,
            user_message,
            previous_response_id=self.previous_response_id,
        )

        response = result.final_output
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
    curriculum: Dict[str, Any],
    previous_response_id: Optional[str] = None,
) -> Dict[str, Any]:
    service = LTGConversationService(vector_store_id, curriculum, previous_response_id)
    return asyncio.run(service.initiate(student))


def continue_ltg_conversation(
    vector_store_id: str,
    previous_response_id: Optional[str],
    user_message: str,
) -> Dict[str, Any]:
    service = LTGConversationService(vector_store_id, {}, previous_response_id)
    return asyncio.run(service.continue_conversation(user_message))


# ---- Full orchestration (validation + DAO + AI) ----

def run_initiate_ltg(user_id: str, period_id: str) -> Dict[str, Any]:
    if not period_id:
        raise ValidationError("Missing period ID")

    period_dao = PeriodDAO()
    student_dao = StudentDAO()
    ltg_conversation_dao = LtgConversationDAO()

    student = student_dao.get_student_by_id(user_id)
    if not student:
        raise Exception("Student not found")

    period = period_dao.get_period_by_id(period_id)
    if not period:
        raise NotFoundError("Invalid period ID")

    vector_store_id = period.get("vector_store_id")
    if not vector_store_id:
        raise Exception("Period does not have a vector store configured")

    curriculum = CurriculumService().get_curriculum(period_id)

    existing_conversation_id = ltg_conversation_dao.get_conversation_id(user_id, period_id)
    if existing_conversation_id:
        return {
            "conversation_id": existing_conversation_id,
            "response": {"message": "Welcome back! Let's continue working on your long-term goal."},
            "resumed": True,
        }

    student_data = {
        "first_name": student.get("first_name", ""),
        "last_name": student.get("last_name", ""),
        "grade": student.get("grade", ""),
        "strength": student.get("strength", []),
        "weakness": student.get("weakness", []),
        "interest": student.get("interest", []),
        "learning_style": student.get("learning_style", []),
    }

    result = initiate_ltg_conversation(vector_store_id=vector_store_id, student=student_data, curriculum=curriculum)

    response_id = result.get("response_id")
    if not response_id:
        raise Exception("Failed to create LTG conversation - no response_id returned")

    conversation_id = str(uuid.uuid4())
    ltg_conversation_dao.upsert_conversation(
        user_id, period_id, conversation_id, last_response_id=response_id
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


def run_continue_ltg(
    user_id: str, conversation_type: str, conversation_id: str,
    message: str, period_id: Optional[str] = None,
) -> Dict[str, Any]:
    period_dao = PeriodDAO()
    ltg_conversation_dao = LtgConversationDAO()

    if not period_id:
        period_id = ltg_conversation_dao.find_period_for_conversation(user_id, conversation_id)
    if not period_id:
        raise Exception("Could not determine period for conversation")

    period = period_dao.get_period_by_id(period_id)
    if not period:
        raise Exception("Period not found")

    vector_store_id = period.get("vector_store_id")
    if not vector_store_id:
        raise Exception("Period does not have a vector store configured")

    last_response_id = ltg_conversation_dao.get_last_response_id(user_id, period_id)

    try:
        result = continue_ltg_conversation(
            vector_store_id=vector_store_id,
            previous_response_id=last_response_id,
            user_message=message,
        )

        new_response_id = result.get("response_id")
        if new_response_id:
            ltg_conversation_dao.update_last_response_id(user_id, period_id, new_response_id)

        reply = result.get("message", "")
        goal_chosen = result.get("goal_chosen", False)
        chosen_goal = result.get("chosen_goal")

        if goal_chosen and chosen_goal:
            StudentLongTermGoalDAO().upsert(user_id, period_id, chosen_goal)

        return {"response": reply, "goal_chosen": goal_chosen}

    except Exception as e:
        return {"error": str(e)}
