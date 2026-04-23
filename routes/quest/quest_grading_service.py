import uuid
from data_access.supabase.weekly_quest_dao import WeeklyQuestDAO
from data_access.supabase.individual_quest_dao import IndividualQuestDAO

from models.weekly_quest import WeeklyQuest
from models.individual_quest import IndividualQuest


class QuestGradingService:

    def __init__(self) -> None:
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()

    def update_individual_quest_status(self, quest_id: str, individual_quest_id: str, status: str) -> dict:
        self.individual_quest_dao.update_individual_quest(individual_quest_id, {"status": status})
        return {
            "message": f"Successfully updated individual quest {individual_quest_id} status to {status}",
            "quest_id": quest_id,
            "individual_quest_id": individual_quest_id,
            "status": status,
        }

    def update_weekly_quest_with_homework(self, homework_data: dict, user_id: str, period_id: str) -> dict:
        weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(user_id, period_id)
        if not weekly_quest:
            raise Exception(f"No weekly quest found for student {user_id} and period {period_id}")

        quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id
        individual_quests = self.individual_quest_dao.get_quests_by_quest_id(quest_id)
        quests_by_week = {q['week']: q for q in individual_quests}

        homework_by_week = {q.get("Week", 1): q for q in homework_data.get("list_of_quests", [])}

        updated_count = 0
        for week, homework_quest in homework_by_week.items():
            existing = quests_by_week.get(week)
            if existing:
                self.individual_quest_dao.update_individual_quest(
                    existing['individual_quest_id'],
                    {
                        "description": homework_quest.get("Name", existing.get('description', '')),
                        "instructions": homework_quest.get("instructions", ""),
                        "rubric": homework_quest.get("rubric", {}),
                    },
                )
            else:
                individual_quest = IndividualQuest(
                    individual_quest_id=str(uuid.uuid4()),
                    quest_id=quest_id,
                    user_id=user_id,
                    period_id=period_id,
                    description=homework_quest.get("Name", ""),
                    skills=homework_quest.get("Skills", ""),
                    week=week,
                    instructions=homework_quest.get("instructions", ""),
                    rubric=homework_quest.get("rubric", {}),
                    status="not_started",
                )
                self.individual_quest_dao.add_individual_quest(individual_quest)
            updated_count += 1

        return {
            "message": f"Successfully updated {updated_count} quests",
            "quest_id": quest_id,
            "updated_quests_count": updated_count,
            "total_quests": len(individual_quests),
        }

    def update_quests_preserving_completed_data(
        self, schedule_data: dict, homework_data: dict, user_id: str, period_id: str
    ) -> dict:
        existing_quests = self.individual_quest_dao.get_quests_by_student_and_period(user_id, period_id)
        existing_by_week = {q['week']: q for q in existing_quests}

        weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(user_id, period_id)

        if not weekly_quest and existing_quests:
            quest_id = existing_quests[0]['quest_id']
            self.weekly_quest_dao.add_weekly_quest(
                WeeklyQuest(quest_id=quest_id, user_id=user_id, period_id=period_id)
            )
            weekly_quest = {'quest_id': quest_id}
        elif not weekly_quest:
            from routes.quest.quest_creation_service import QuestCreationService
            creator = QuestCreationService()
            schedule_result = creator.save_schedule_to_weekly_quests(schedule_data, user_id, period_id)
            homework_result = self.update_weekly_quest_with_homework(homework_data, user_id, period_id)
            return {
                "message": "Created new quest structure",
                "schedule_result": schedule_result,
                "homework_result": homework_result,
                "preserved_quests": 0,
                "updated_quests": 0,
                "created_quests": len(schedule_data.get("list_of_quests", [])),
                "total_quests": len(schedule_data.get("list_of_quests", [])),
            }

        quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id
        homework_by_week = {q.get("Week", 1): q for q in homework_data.get("list_of_quests", [])}

        updated_count = preserved_count = created_count = 0

        for quest_data in schedule_data.get("list_of_quests", []):
            week = quest_data.get("Week", 1)
            existing = existing_by_week.get(week)
            homework_quest = homework_by_week.get(week, {})

            if existing:
                is_locked = existing.get('grade') is not None or existing.get('status') in ('completed', 'in_progress')
                if is_locked:
                    new_skills = quest_data.get("Skills", existing.get('skills', ''))
                    if new_skills != existing.get('skills', ''):
                        self.individual_quest_dao.update_individual_quest(
                            existing['individual_quest_id'], {'skills': new_skills}
                        )
                    preserved_count += 1
                else:
                    self.individual_quest_dao.update_individual_quest(
                        existing['individual_quest_id'],
                        {
                            "description": homework_quest.get("Name", quest_data.get("Name", "")),
                            "skills": quest_data.get("Skills", ""),
                            "instructions": homework_quest.get("instructions", ""),
                            "rubric": homework_quest.get("rubric", {}),
                        },
                    )
                    updated_count += 1
            else:
                self.individual_quest_dao.add_individual_quest(IndividualQuest(
                    individual_quest_id=str(uuid.uuid4()),
                    quest_id=quest_id,
                    user_id=user_id,
                    period_id=period_id,
                    description=homework_quest.get("Name", quest_data.get("Name", "")),
                    skills=quest_data.get("Skills", ""),
                    week=week,
                    instructions=homework_quest.get("instructions", ""),
                    rubric=homework_quest.get("rubric", {}),
                    status="not_started",
                ))
                created_count += 1

        self.weekly_quest_dao.update_weekly_quest(quest_id, {})
        total = len(self.individual_quest_dao.get_quests_by_student_and_period(user_id, period_id))
        return {
            "message": "Successfully updated quests preserving completed data",
            "preserved_quests": preserved_count,
            "updated_quests": updated_count,
            "created_quests": created_count,
            "total_quests": total,
            "quest_id": quest_id,
        }
