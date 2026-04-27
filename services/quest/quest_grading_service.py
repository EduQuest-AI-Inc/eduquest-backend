import uuid
from data_access.quest_dao import QuestDAO
from models.quest import Quest


class QuestGradingService:

    def __init__(self) -> None:
        self.quest_dao = QuestDAO()

    def update_quest_status(self, quest_id: str, status: str) -> dict:
        self.quest_dao.update_quest_status(quest_id, status)
        return {
            "message": f"Successfully updated quest {quest_id} status to {status}",
            "quest_id": quest_id,
            "status": status,
        }

    def update_quests_preserving_completed_data(
        self, schedule_data: dict, homework_data: dict, user_id: str, period_id: str
    ) -> dict:
        existing_quests = self.quest_dao.get_quests_by_student_and_period(user_id, period_id)
        existing_by_week = {q['week']: q for q in existing_quests}
        homework_by_week = {q.get("Week", 1): q for q in homework_data.get("list_of_quests", [])}

        updated_count = preserved_count = created_count = 0

        for quest_data in schedule_data.get("list_of_quests", []):
            week = quest_data.get("Week", 1)
            existing = existing_by_week.get(week)
            homework_quest = homework_by_week.get(week, {})

            if existing:
                is_locked = (
                    existing.get('grade') is not None
                    or existing.get('status') in ('completed', 'in_progress')
                )
                if is_locked:
                    new_skills = quest_data.get("Skills", existing.get('skills', ''))
                    if new_skills != existing.get('skills', ''):
                        self.quest_dao.update_quest(existing['quest_id'], {'skills': new_skills})
                    preserved_count += 1
                else:
                    self.quest_dao.update_quest(
                        existing['quest_id'],
                        {
                            "description": homework_quest.get("Name", quest_data.get("Name", "")),
                            "skills": quest_data.get("Skills", ""),
                            "instructions": homework_quest.get("instructions", ""),
                            "rubric": homework_quest.get("rubric", {}),
                        },
                    )
                    updated_count += 1
            else:
                quest = Quest(
                    quest_id=str(uuid.uuid4()),
                    user_id=user_id,
                    period_id=period_id,
                    description=homework_quest.get("Name", quest_data.get("Name", "")),
                    skills=quest_data.get("Skills", ""),
                    week=week,
                    instructions=homework_quest.get("instructions", ""),
                    rubric=homework_quest.get("rubric", {}),
                    status="not_started",
                )
                self.quest_dao.add_quest(quest)
                created_count += 1

        total = len(self.quest_dao.get_quests_by_student_and_period(user_id, period_id))
        return {
            "message": "Successfully updated quests preserving completed data",
            "preserved_quests": preserved_count,
            "updated_quests": updated_count,
            "created_quests": created_count,
            "total_quests": total,
        }
