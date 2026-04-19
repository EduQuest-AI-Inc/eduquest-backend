import os
import json

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.weekly_quest_dao import WeeklyQuestDAO
    from data_access.supabase.individual_quest_dao import IndividualQuestDAO
else:
    from data_access.weekly_quest_dao import WeeklyQuestDAO
    from data_access.individual_quest_dao import IndividualQuestDAO


class QuestRetrievalService:

    def __init__(self):
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()

    def get_weekly_quests_for_student(self, student_id: str, period_id: str):
        return self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)

    def get_individual_quests_for_student(self, student_id: str) -> list:
        return self.individual_quest_dao.get_quests_by_student(student_id)

    def get_individual_quests_for_student_and_period(self, student_id: str, period_id: str) -> list:
        return self.individual_quest_dao.get_quests_by_student_and_period(student_id, period_id)

    def get_individual_quest_by_id(self, quest_id: str, individual_quest_id: str):
        return self.individual_quest_dao.get_individual_quest_by_id(individual_quest_id)

    def verify_quest_structure(self, student_id: str, period_id: str) -> dict:
        weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
        if not weekly_quest:
            return {"error": "No weekly quest found"}

        quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id
        individual_quests = self.individual_quest_dao.get_quests_by_quest_id(quest_id)

        return {
            "weekly_quest": {"quest_id": quest_id, "student_id": student_id, "period_id": period_id},
            "individual_quests": {
                "total_count": len(individual_quests),
                "quest_id": quest_id,
                "individual_quest_ids": [q["individual_quest_id"] for q in individual_quests],
                "weeks": [q["week"] for q in individual_quests],
            },
            "verification": {
                "individual_quest_count": len(individual_quests),
                "all_share_same_quest_id": all(q["quest_id"] == quest_id for q in individual_quests),
            },
        }

    @staticmethod
    def parse_grade_data(grade_str: str) -> dict:
        if not grade_str:
            return {"detailed_grade": None, "overall_score": None, "display_grade": "Not graded"}
        try:
            grade_data = json.loads(grade_str)
            if isinstance(grade_data, dict) and "detailed_grade" in grade_data:
                return {
                    "detailed_grade": grade_data.get("detailed_grade"),
                    "overall_score": grade_data.get("overall_score", "Score not available"),
                    "display_grade": grade_data.get("overall_score", "Score not available"),
                }
        except (json.JSONDecodeError, TypeError):
            pass
        return {"detailed_grade": None, "overall_score": grade_str, "display_grade": grade_str}

    @staticmethod
    def format_grade_for_display(grade_str: str) -> str:
        return QuestRetrievalService.parse_grade_data(grade_str)["display_grade"]

    @staticmethod
    def attach_grade_display(quest: dict) -> None:
        """Parse grade data and attach display fields to a quest dict in-place."""
        grade_info = QuestRetrievalService.parse_grade_data(quest.get('grade'))
        quest['grade_info'] = grade_info
        quest['display_grade'] = grade_info.get('display_grade', 'Not graded')
