import uuid
from data_access.quest_dao import QuestDAO
from models.quest import Quest


class QuestCreationService:

    def __init__(self, quest_dao=None, jwt: str | None = None) -> None:
        self.quest_dao = quest_dao or QuestDAO(jwt=jwt)

    def save_quests_from_schedule(self, schedule_data: dict, user_id: str, period_id: str) -> dict:
        """Create Quest rows for each entry in a schedule. Returns summary dict."""
        created = []
        for quest_data in schedule_data.get("list_of_quests", []):
            quest = Quest(
                quest_id=str(uuid.uuid4()),
                user_id=user_id,
                period_id=period_id,
                description=quest_data.get("Name", ""),
                skills=quest_data.get("Skills", ""),
                week=quest_data.get("Week", 1),
                instructions="",
                rubric={},
                status="not_started",
            )
            self.quest_dao.add_quest(quest)
            created.append(quest.quest_id)

        return {
            "message": f"Successfully created {len(created)} quests",
            "created_quest_count": len(created),
            "quest_ids": created,
        }

    def create_quests_from_homework(self, homework_data: dict, user_id: str, period_id: str) -> dict:
        """Create or update Quest rows from detailed homework agent output."""
        created = []
        for quest_data in homework_data.get("list_of_quests", []):
            quest = Quest(
                quest_id=str(uuid.uuid4()),
                user_id=user_id,
                period_id=period_id,
                description=quest_data.get("Name", ""),
                skills=quest_data.get("Skills", ""),
                week=quest_data.get("Week", 1),
                instructions=quest_data.get("instructions", ""),
                rubric=quest_data.get("rubric", {}),
                status="not_started",
            )
            self.quest_dao.add_quest(quest)
            created.append(quest.quest_id)

        return {
            "message": f"Successfully created {len(created)} quests",
            "created_quest_count": len(created),
            "quest_ids": created,
        }
