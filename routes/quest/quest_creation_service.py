import uuid
from data_access.supabase.weekly_quest_dao import WeeklyQuestDAO
from data_access.supabase.individual_quest_dao import IndividualQuestDAO

from models.weekly_quest import WeeklyQuest
from models.individual_quest import IndividualQuest


class QuestCreationService:

    def __init__(self) -> None:
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()

    def save_schedule_to_weekly_quests(self, schedule_data: dict, user_id: str, period_id: str) -> dict:
        quest_id = str(uuid.uuid4())
        individual_quests = []

        for quest_data in schedule_data.get("list_of_quests", []):
            individual_quest = IndividualQuest(
                individual_quest_id=str(uuid.uuid4()),
                quest_id=quest_id,
                user_id=user_id,
                period_id=period_id,
                description=quest_data.get("Name", ""),
                skills=quest_data.get("Skills", ""),
                week=quest_data.get("Week", 1),
                instructions="",
                rubric={},
                status="not_started",
            )
            individual_quests.append(individual_quest)

        weekly_quest = WeeklyQuest(quest_id=quest_id, user_id=user_id, period_id=period_id)
        self.weekly_quest_dao.add_weekly_quest(weekly_quest)
        for iq in individual_quests:
            self.individual_quest_dao.add_individual_quest(iq)

        return {
            "message": f"Successfully saved weekly quest list with {len(individual_quests)} individual quests",
            "quest_id": quest_id,
            "individual_quest_count": len(individual_quests),
            "individual_quest_ids": [q.individual_quest_id for q in individual_quests],
        }

    def create_individual_quests_from_homework(self, homework_data: dict, user_id: str, period_id: str) -> dict:
        weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(user_id, period_id)
        if not weekly_quest:
            raise Exception(f"No weekly quest found for student {user_id} and period {period_id}")

        quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id
        created_count = 0

        for quest_data in homework_data.get("list_of_quests", []):
            individual_quest = IndividualQuest(
                individual_quest_id=str(uuid.uuid4()),
                quest_id=quest_id,
                user_id=user_id,
                period_id=period_id,
                description=quest_data.get("Name", ""),
                skills=quest_data.get("Skills", ""),
                week=quest_data.get("Week", 1),
                instructions=quest_data.get("instructions", ""),
                rubric=quest_data.get("rubric", {}),
                status="not_started",
            )
            self.individual_quest_dao.add_individual_quest(individual_quest)
            created_count += 1

        return {
            "message": f"Successfully created {created_count} individual quests",
            "quest_id": quest_id,
            "created_quests_count": created_count,
        }
