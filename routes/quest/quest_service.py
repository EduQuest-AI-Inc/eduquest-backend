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
            # Create one quest_id for the entire list of quests for this period
            quest_id = str(uuid.uuid4())
            
            # Convert schedule quests to WeeklyQuestItem objects for weekly quest table
            quest_items = []
            individual_quests = []
            
            for quest_data in schedule_data.get("list_of_quests", []):
                individual_quest_id = str(uuid.uuid4())
                
                # Create WeeklyQuestItem for weekly quest table
                quest_item = WeeklyQuestItem(
                    individual_quest_id=individual_quest_id,
                    name=quest_data.get("Name", ""),
                    skills=quest_data.get("Skills", ""),
                    week=quest_data.get("Week", 1),
                    status="not_started"
                )
                quest_items.append(quest_item)
                
                # Create IndividualQuest for individual quest table
                individual_quest = IndividualQuest(
                    individual_quest_id=individual_quest_id,
                    quest_id=quest_id,  # Same quest_id for all 18 quests
                    student_id=student_id,
                    period_id=period_id,
                    description=quest_data.get("Name", ""),
                    skills=quest_data.get("Skills", ""),
                    Week=quest_data.get("Week", 1),
                    instructions="",  # Will be filled by homework agent
                    rubric={},  # Will be filled by homework agent
                    status="not_started"
                )
                individual_quests.append(individual_quest)
            
            # Create the weekly quest containing all individual quests
            weekly_quest = WeeklyQuest(
                quest_id=quest_id,
                student_id=student_id,
                period_id=period_id,
                quests=quest_items
            )
            
            # Save to weekly quest table
            self.weekly_quest_dao.add_weekly_quest(weekly_quest)
            
            # Save to individual quest table
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
                    description=quest_data.get("Name", ""),  # Map Name to description
                    skills=quest_data.get("Skills", ""),
                    Week=quest_data.get("Week", 1),
                    instructions=quest_data.get("instructions", ""),  # Map instructions to instructions
                    rubric=quest_data.get("rubric", {}),  # Map rubric to rubric
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
            
            # Get the existing weekly quest for this student and period
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                raise Exception(f"No weekly quest found for student {student_id} and period {period_id}")
            
            print(f"DEBUG: Found existing weekly quest: {weekly_quest.quest_id}")
            print(f"DEBUG: Existing quests count: {len(weekly_quest.quests)}")
            
            # Create a mapping of week numbers to homework data
            homework_by_week = {}
            for quest_data in homework_data.get("list_of_quests", []):
                week = quest_data.get("Week", 1)
                homework_by_week[week] = quest_data
            
            print(f"DEBUG: Homework data by week: {homework_by_week}")
            
            # Update each quest in the weekly quest list with detailed homework information
            updated_count = 0
            for quest_item in weekly_quest.quests:
                week = quest_item.week
                if week in homework_by_week:
                    homework_quest = homework_by_week[week]
                    
                    # Update the quest item with detailed homework information
                    quest_item.description = homework_quest.get("Name", quest_item.name)
                    quest_item.instructions = homework_quest.get("instructions", "")
                    quest_item.rubric = homework_quest.get("rubric", {})
                    quest_item.last_updated_at = datetime.now(timezone.utc).isoformat()
                    
                    # Also update the corresponding individual quest in the individual quest table
                    self.individual_quest_dao.update_individual_quest_by_individual_id(
                        quest_item.individual_quest_id,
                        {
                            "description": homework_quest.get("Name", quest_item.name),
                            "instructions": homework_quest.get("instructions", ""),
                            "rubric": homework_quest.get("rubric", {})
                        }
                    )
                    
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
            # Get weekly quest
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                return {"error": "No weekly quest found"}
            
            # Get individual quests that share the same quest_id
            individual_quests = self.individual_quest_dao.get_quests_by_quest_id(weekly_quest.quest_id)
            
            # Verify structure
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
                    "quest_id": weekly_quest.quest_id,  # Should be the same for all
                    "individual_quest_ids": [quest["individual_quest_id"] for quest in individual_quests],
                    "weeks": [quest["Week"] for quest in individual_quests]
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