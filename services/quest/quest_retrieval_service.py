from data_access.quest_dao import QuestDAO


class QuestRetrievalService:

    def __init__(self, quest_dao=None, jwt: str | None = None) -> None:
        self.quest_dao = quest_dao or QuestDAO(jwt=jwt)

    def get_quests_for_student(self, user_id: str) -> list:
        return self.quest_dao.get_quests_by_student(user_id)

    def get_quests_for_student_and_period(self, user_id: str, period_id: str) -> list:
        return self.quest_dao.get_quests_by_student_and_period(user_id, period_id)

    def get_quest_by_id(self, quest_id: str):
        return self.quest_dao.get_quest_by_id(quest_id)

    def verify_quest_structure(self, user_id: str, period_id: str) -> dict:
        quests = self.quest_dao.get_quests_by_student_and_period(user_id, period_id)
        if not quests:
            return {"error": "No quests found for this student and period"}
        return {
            "quests": {
                "total_count": len(quests),
                "quest_ids": [q["quest_id"] for q in quests],
                "weeks": [q["week"] for q in quests],
            },
        }

    @staticmethod
    def parse_grade_data(grade) -> dict:
        """Parse a grade value (dict or legacy string) into a display dict."""
        if grade is None:
            return {"detailed_grade": None, "overall_score": None, "display_grade": "Not graded"}
        if isinstance(grade, dict):
            overall = grade.get("overall_score", "Score not available")
            return {
                "detailed_grade": grade.get("detailed_grade"),
                "overall_score": overall,
                "display_grade": overall,
            }
        # Legacy: grade stored as a plain string
        return {"detailed_grade": None, "overall_score": str(grade), "display_grade": str(grade)}

    @staticmethod
    def attach_grade_display(quest: dict) -> None:
        """Parse grade data and attach display fields to a quest dict in-place."""
        grade_info = QuestRetrievalService.parse_grade_data(quest.get('grade'))
        quest['grade_info'] = grade_info
        quest['display_grade'] = grade_info.get('display_grade', 'Not graded')
