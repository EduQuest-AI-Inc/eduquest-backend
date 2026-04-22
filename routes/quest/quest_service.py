"""
Thin orchestrator — delegates to focused sub-services.
Kept for backwards compatibility so callers importing QuestService remain unchanged.
"""
from routes.quest.quest_creation_service import QuestCreationService
from routes.quest.quest_retrieval_service import QuestRetrievalService
from routes.quest.quest_grading_service import QuestGradingService
from typing import Any, Dict, List, Optional, Union


class QuestService:

    def __init__(self) -> None:
        self._creation = QuestCreationService()
        self._retrieval = QuestRetrievalService()
        self._grading = QuestGradingService()

    # Creation
    def save_schedule_to_weekly_quests(self, schedule_data, user_id, period_id):
        return self._creation.save_schedule_to_weekly_quests(schedule_data, user_id, period_id)

    def create_individual_quests_from_homework(self, homework_data, user_id, period_id):
        return self._creation.create_individual_quests_from_homework(homework_data, user_id, period_id)

    # Retrieval
    def get_weekly_quests_for_student(self, user_id, period_id):
        return self._retrieval.get_weekly_quests_for_student(user_id, period_id)

    def get_individual_quests_for_student(self, user_id):
        return self._retrieval.get_individual_quests_for_student(user_id)

    def get_individual_quests_for_student_and_period(self, user_id: str, period_id: str) -> List[Any]:
        return self._retrieval.get_individual_quests_for_student_and_period(user_id, period_id)

    def get_individual_quest_by_id(self, quest_id, individual_quest_id):
        return self._retrieval.get_individual_quest_by_id(quest_id, individual_quest_id)

    def verify_quest_structure(self, user_id, period_id):
        return self._retrieval.verify_quest_structure(user_id, period_id)

    @staticmethod
    def parse_grade_data(grade_str: Optional[str]) -> Dict[str, Optional[Union[Dict[str, int], str, Dict[str, str]]]]:
        return QuestRetrievalService.parse_grade_data(grade_str)

    @staticmethod
    def format_grade_for_display(grade_str: Optional[str]) -> str:
        return QuestRetrievalService.format_grade_for_display(grade_str)

    # Grading / updates
    def update_individual_quest_status(self, quest_id, individual_quest_id, status):
        return self._grading.update_individual_quest_status(quest_id, individual_quest_id, status)

    def update_weekly_quest_with_homework(self, homework_data, user_id, period_id):
        return self._grading.update_weekly_quest_with_homework(homework_data, user_id, period_id)

    def update_quests_preserving_completed_data(self, schedule_data, homework_data, user_id, period_id):
        return self._grading.update_quests_preserving_completed_data(schedule_data, homework_data, user_id, period_id)

    def save_homework_to_individual_quests(self, homework_data, user_id, period_id):
        return self._creation.create_individual_quests_from_homework(homework_data, user_id, period_id)
