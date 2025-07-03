from data_access.weekly_quest_dao import WeeklyQuestDAO
from data_access.individual_quest_dao import IndividualQuestDAO
from models.weekly_quest import WeeklyQuest
from models.weekly_quest_item import WeeklyQuestItem
from models.individual_quest import IndividualQuest
from datetime import datetime, timezone
import uuid

class QuestService:
    def __init__(self):
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()

    def save_schedule_to_weekly_quests(self, schedule_data: dict, student_id: str, period_id: str) -> dict:
        """Save the schedule from SchedulesAgent to both weekly_quest table and individual_quest table."""
        try:
            quest_id = str(uuid.uuid4())
            
            quest_items = []
            individual_quests = []
            
            for quest_data in schedule_data.get("list_of_quests", []):
                individual_quest_id = str(uuid.uuid4())
                
                quest_item = WeeklyQuestItem(
                    individual_quest_id=individual_quest_id,
                    name=quest_data.get("Name", ""),
                    skills=quest_data.get("Skills", ""),
                    week=quest_data.get("Week", 1),
                    status="not_started"
                )
                quest_items.append(quest_item)
                
                individual_quest = IndividualQuest(
                    individual_quest_id=individual_quest_id,
                    quest_id=quest_id,  
                    student_id=student_id,
                    period_id=period_id,
                    description=quest_data.get("Name", ""),
                    skills=quest_data.get("Skills", ""),
                    week=quest_data.get("Week", 1),
                    instructions="",  # will be filled by homework agent
                    rubric={},  # will be filled by homework agent
                    status="not_started"
                )
                individual_quests.append(individual_quest)
            
            weekly_quest = WeeklyQuest(
                quest_id=quest_id,
                student_id=student_id,
                period_id=period_id,
                quests=quest_items
            )
            
            self.weekly_quest_dao.add_weekly_quest(weekly_quest)
            
            for individual_quest in individual_quests:
                self.individual_quest_dao.add_individual_quest(individual_quest)
            
            return {
                "message": f"Successfully saved weekly quest list with {len(quest_items)} individual quests",
                "quest_id": quest_id,
                "individual_quest_count": len(quest_items),
                "individual_quest_ids": [quest.individual_quest_id for quest in individual_quests]
            }
            
        except Exception as e:
            print(f"Error saving schedule to weekly quests: {str(e)}")
            raise Exception(f"Failed to save schedule: {str(e)}")

    def save_homework_to_individual_quests(self, homework_data: dict, student_id: str, period_id: str) -> dict:
        """Save the homework from HomeworkAgent to individual_quest table."""
        try:
            print(f"DEBUG: Received homework_data: {homework_data}")
            print(f"DEBUG: homework_data type: {type(homework_data)}")
            print(f"DEBUG: list_of_quests: {homework_data.get('list_of_quests', [])}")
            
            saved_quests = []
            
            for quest_data in homework_data.get("list_of_quests", []):
                print(f"DEBUG: Processing quest_data: {quest_data}")
                quest_id = str(uuid.uuid4())
                individual_quest_id = str(uuid.uuid4())
                
                individual_quest = IndividualQuest(
                    individual_quest_id=individual_quest_id,
                    quest_id=quest_id,
                    student_id=student_id,
                    period_id=period_id,
                    description=quest_data.get("Name", ""),  
                    skills=quest_data.get("Skills", ""),
                    week=quest_data.get("Week", 1),
                    instructions=quest_data.get("instructions", ""),  
                    rubric=quest_data.get("rubric", {}),  
                    status="not_started"
                )
                
                print(f"DEBUG: Created IndividualQuest: {individual_quest.model_dump()}")
                
                self.individual_quest_dao.add_individual_quest(individual_quest)
                saved_quests.append(quest_id)
            
            return {
                "message": f"Successfully saved {len(saved_quests)} individual quests",
                "quest_ids": saved_quests
            }
            
        except Exception as e:
            print(f"Error saving homework to individual quests: {str(e)}")
            raise Exception(f"Failed to save homework: {str(e)}")

    def update_weekly_quest_with_homework(self, homework_data: dict, student_id: str, period_id: str) -> dict:
        """Update both weekly quest table and individual quest table with detailed homework information from HomeworkAgent."""
        try:
            print(f"DEBUG: Updating weekly quest with homework_data: {homework_data}")
            
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                raise Exception(f"No weekly quest found for student {student_id} and period {period_id}")
            
            print(f"DEBUG: Found existing weekly quest: {weekly_quest.quest_id}")
            print(f"DEBUG: Existing quests count: {len(weekly_quest.quests)}")
            
            homework_by_week = {}
            for quest_data in homework_data.get("list_of_quests", []):
                week = quest_data.get("Week", 1)
                homework_by_week[week] = quest_data
            
            print(f"DEBUG: Homework data by week: {homework_by_week}")
            
            updated_count = 0
            for quest_item in weekly_quest.quests:
                week = quest_item.week
                if week in homework_by_week:
                    homework_quest = homework_by_week[week]
                    
                    # Update the weekly quest item
                    quest_item.description = homework_quest.get("Name", quest_item.name)
                    quest_item.instructions = homework_quest.get("instructions", "")
                    quest_item.rubric = homework_quest.get("rubric", {})
                    quest_item.last_updated_at = datetime.now(timezone.utc).isoformat()
                    
                    # Update the individual quest in the database
                    try:
                        self.individual_quest_dao.update_individual_quest_by_individual_id(
                            quest_item.individual_quest_id,
                            {
                                "description": homework_quest.get("Name", quest_item.name),
                                "instructions": homework_quest.get("instructions", ""),
                                "rubric": homework_quest.get("rubric", {})
                            }
                        )
                        print(f"DEBUG: Successfully updated individual quest {quest_item.individual_quest_id} for week {week}")
                    except Exception as e:
                        print(f"DEBUG: Error updating individual quest {quest_item.individual_quest_id}: {str(e)}")
                        # Try to create a new individual quest if update fails
                        try:
                            individual_quest = IndividualQuest(
                                individual_quest_id=quest_item.individual_quest_id,
                                quest_id=weekly_quest.quest_id,
                                student_id=student_id,
                                period_id=period_id,
                                description=homework_quest.get("Name", quest_item.name),
                                skills=quest_item.skills,
                                week=week,
                                instructions=homework_quest.get("instructions", ""),
                                rubric=homework_quest.get("rubric", {}),
                                status="not_started"
                            )
                            self.individual_quest_dao.add_individual_quest(individual_quest)
                            print(f"DEBUG: Created new individual quest {quest_item.individual_quest_id} for week {week}")
                        except Exception as create_error:
                            print(f"DEBUG: Error creating individual quest {quest_item.individual_quest_id}: {str(create_error)}")
                    
                    updated_count += 1
                    print(f"DEBUG: Updated quest for week {week}")
            
            # Save the updated weekly quest
            self.weekly_quest_dao.add_weekly_quest(weekly_quest)
            
            return {
                "message": f"Successfully updated {updated_count} quests in both weekly quest list and individual quest table",
                "quest_id": weekly_quest.quest_id,
                "updated_quests_count": updated_count,
                "total_quests": len(weekly_quest.quests)
            }
            
        except Exception as e:
            print(f"Error updating weekly quest with homework: {str(e)}")
            raise Exception(f"Failed to update weekly quest: {str(e)}")

    def get_weekly_quests_for_student(self, student_id: str, period_id: str) -> WeeklyQuest:
        """Get the weekly quest list for a student in a specific period."""
        return self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)

    def get_individual_quests_for_student(self, student_id: str) -> list:
        """Get all individual quests for a student."""
        return self.individual_quest_dao.get_quests_by_student(student_id)

    def get_individual_quests_for_student_and_period(self, student_id: str, period_id: str) -> list:
        return self.individual_quest_dao.get_quests_by_student_and_period(student_id, period_id)

    def update_individual_quest_status(self, weekly_quest_id: str, individual_quest_id: str, status: str) -> dict:
        """Update the status of a specific individual quest within a weekly quest list."""
        try:
            self.weekly_quest_dao.update_individual_quest_in_weekly_quest(
                weekly_quest_id, 
                individual_quest_id, 
                {"status": status}
            )
            
            return {
                "message": f"Successfully updated individual quest {individual_quest_id} status to {status}",
                "weekly_quest_id": weekly_quest_id,
                "individual_quest_id": individual_quest_id,
                "status": status
            }
            
        except Exception as e:
            print(f"Error updating individual quest status: {str(e)}")
            raise Exception(f"Failed to update quest status: {str(e)}")

    def get_individual_quest_by_id(self, weekly_quest_id: str, individual_quest_id: str) -> WeeklyQuestItem:
        """Get a specific individual quest from a weekly quest list."""
        weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_id(weekly_quest_id)
        if not weekly_quest:
            return None
        
        for quest in weekly_quest.quests:
            if quest.individual_quest_id == individual_quest_id:
                return quest
        
        return None

    def verify_quest_structure(self, student_id: str, period_id: str) -> dict:
        """Verify that quests are saved correctly in both tables."""
        try:
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                return {"error": "No weekly quest found"}
            
            individual_quests = self.individual_quest_dao.get_quests_by_quest_id(weekly_quest.quest_id)
            
            #verifying
            verification = {
                "weekly_quest": {
                    "quest_id": weekly_quest.quest_id,
                    "student_id": weekly_quest.student_id,
                    "period_id": weekly_quest.period_id,
                    "quests_count": len(weekly_quest.quests),
                    "individual_quest_ids": [quest.individual_quest_id for quest in weekly_quest.quests]
                },
                "individual_quests": {
                    "total_count": len(individual_quests),
                    "quest_id": weekly_quest.quest_id,  
                    "individual_quest_ids": [quest["individual_quest_id"] for quest in individual_quests],
                    "weeks": [quest["week"] for quest in individual_quests]
                },
                "verification": {
                    "weekly_quest_count": len(weekly_quest.quests),
                    "individual_quest_count": len(individual_quests),
                    "counts_match": len(weekly_quest.quests) == len(individual_quests),
                    "all_share_same_quest_id": all(quest["quest_id"] == weekly_quest.quest_id for quest in individual_quests),
                    "individual_ids_match": set(quest.individual_quest_id for quest in weekly_quest.quests) == set(quest["individual_quest_id"] for quest in individual_quests)
                }
            }
            
            return verification
            
        except Exception as e:
            print(f"Error verifying quest structure: {str(e)}")
            return {"error": f"Failed to verify quest structure: {str(e)}"}

    def create_individual_quests_from_homework(self, homework_data: dict, student_id: str, period_id: str) -> dict:
        """Create individual quests from homework data when they don't exist in the database."""
        try:
            print(f"DEBUG: Creating individual quests from homework_data: {homework_data}")
            
            # Get the weekly quest to get the quest_id
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                raise Exception(f"No weekly quest found for student {student_id} and period {period_id}")
            
            quest_id = weekly_quest.quest_id
            created_count = 0
            
            for quest_data in homework_data.get("list_of_quests", []):
                individual_quest_id = str(uuid.uuid4())
                
                individual_quest = IndividualQuest(
                    individual_quest_id=individual_quest_id,
                    quest_id=quest_id,
                    student_id=student_id,
                    period_id=period_id,
                    description=quest_data.get("Name", ""),
                    skills=quest_data.get("Skills", ""),
                    week=quest_data.get("Week", 1),
                    instructions=quest_data.get("instructions", ""),
                    rubric=quest_data.get("rubric", {}),
                    status="not_started"
                )
                
                self.individual_quest_dao.add_individual_quest(individual_quest)
                created_count += 1
                print(f"DEBUG: Created individual quest {individual_quest_id} for week {quest_data.get('Week', 1)}")
            
            return {
                "message": f"Successfully created {created_count} individual quests",
                "quest_id": quest_id,
                "created_quests_count": created_count
            }
            
        except Exception as e:
            print(f"Error creating individual quests from homework: {str(e)}")
            raise Exception(f"Failed to create individual quests: {str(e)}") 