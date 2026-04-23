import uuid
from typing import Any
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from data_access.supabase.period_dao import PeriodDAO
from data_access.supabase.student_dao import StudentDAO
from data_access.supabase.ltg_conversation_dao import LtgConversationDAO

from routes.conversation.ltg_service import (
    initiate_ltg_conversation as ltg_initiate,
    continue_ltg_conversation as ltg_continue,
)


class PeriodLTGService:

    def __init__(self) -> None:
        self.period_dao = PeriodDAO()
        self.student_dao = StudentDAO()
        self.ltg_conversation_dao = LtgConversationDAO()

    def initiate_ltg_conversation(self, user_id: str, period_id: str) -> Any:
        if not period_id:
            raise ValidationError("Missing period ID")

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise NotFoundError("Invalid period ID")

        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise Exception("Period does not have a vector store configured")

        existing_conversation_id = self.ltg_conversation_dao.get_conversation_id(user_id, period_id)
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

        result = ltg_initiate(vector_store_id=vector_store_id, student=student_data)

        response_id = result.get("response_id")
        if not response_id:
            raise Exception("Failed to create LTG conversation - no response_id returned")

        conversation_id = str(uuid.uuid4())
        self.ltg_conversation_dao.upsert_conversation(
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

    def continue_ltg_conversation(
        self, user_id: str, conversation_type: str, conversation_id: str,
        message: str, period_id: str = None
    ) -> Any:

        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        if not period_id:
            period_id = self.ltg_conversation_dao.find_period_for_conversation(user_id, conversation_id)
        if not period_id:
            raise Exception("Could not determine period for conversation")

        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception("Period not found")

        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise Exception("Period does not have a vector store configured")

        last_response_id = self.ltg_conversation_dao.get_last_response_id(user_id, period_id)

        try:
            result = ltg_continue(
                vector_store_id=vector_store_id,
                previous_response_id=last_response_id,
                user_message=message,
            )

            new_response_id = result.get("response_id")
            if new_response_id:
                self.ltg_conversation_dao.update_last_response_id(user_id, period_id, new_response_id)

            reply = result.get("message", "")
            goal_chosen = result.get("goal_chosen", False)
            chosen_goal = result.get("chosen_goal")

            if goal_chosen and chosen_goal:
                self.student_dao.update_long_term_goal(user_id, period_id, chosen_goal)

            return {"response": reply, "goal_chosen": goal_chosen}

        except Exception as e:
            return {"error": str(e)}
