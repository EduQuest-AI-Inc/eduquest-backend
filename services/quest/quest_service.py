"""Thin orchestrator — delegates to focused sub-services."""
from services.quest.quest_creation_service import QuestCreationService
from services.quest.quest_retrieval_service import QuestRetrievalService
from services.quest.quest_grading_service import QuestGradingService
from typing import Any, List


class QuestService:

    def __init__(self) -> None:
        self._creation = QuestCreationService()
        self._retrieval = QuestRetrievalService()
        self._grading = QuestGradingService()

    # Creation
    def save_quests_from_schedule(self, schedule_data, user_id, period_id):
        return self._creation.save_quests_from_schedule(schedule_data, user_id, period_id)

    def create_quests_from_homework(self, homework_data, user_id, period_id):
        return self._creation.create_quests_from_homework(homework_data, user_id, period_id)

    # Retrieval
    def get_quests_for_student(self, user_id: str) -> list:
        return self._retrieval.get_quests_for_student(user_id)

    def get_quests_for_student_and_period(self, user_id: str, period_id: str) -> List[Any]:
        return self._retrieval.get_quests_for_student_and_period(user_id, period_id)

    def get_quest_by_id(self, quest_id: str):
        return self._retrieval.get_quest_by_id(quest_id)

    def verify_quest_structure(self, user_id, period_id):
        return self._retrieval.verify_quest_structure(user_id, period_id)

    # Grading / updates
    def update_quest_status(self, quest_id: str, status: str):
        return self._grading.update_quest_status(quest_id, status)

    def update_completed_steps(self, quest_id: str, completed_steps: list) -> None:
        self._grading.update_completed_steps(quest_id, completed_steps)

    def update_quest_grade_and_feedback(self, quest_id: str, grade: dict, feedback: str) -> None:
        self._grading.update_quest_grade_and_feedback(quest_id, grade, feedback)

    def update_quests_preserving_completed_data(self, schedule_data, homework_data, user_id, period_id):
        return self._grading.update_quests_preserving_completed_data(schedule_data, homework_data, user_id, period_id)
