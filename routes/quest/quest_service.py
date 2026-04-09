import os
if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.weekly_quest_dao import WeeklyQuestDAO
    from data_access.supabase.individual_quest_dao import IndividualQuestDAO
else:
    from data_access.weekly_quest_dao import WeeklyQuestDAO
    from data_access.individual_quest_dao import IndividualQuestDAO

from models.weekly_quest import WeeklyQuest
from models.individual_quest import IndividualQuest
from datetime import datetime, timezone
import uuid
import json

class QuestService:
    def __init__(self):
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()

    def save_schedule_to_weekly_quests(self, schedule_data: dict, student_id: str, period_id: str) -> dict:
        """Save a schedule to both weekly_quest table and individual_quest table."""
        try:
            quest_id = str(uuid.uuid4())

            individual_quests = []

            for quest_data in schedule_data.get("list_of_quests", []):
                individual_quest_id = str(uuid.uuid4())

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
            )

            print(f"DEBUG: Saving weekly quest with quest_id={quest_id}, student_id={student_id}, period_id={period_id}")
            self.weekly_quest_dao.add_weekly_quest(weekly_quest)
            print(f"DEBUG: Successfully saved weekly quest to database")

            for individual_quest in individual_quests:
                self.individual_quest_dao.add_individual_quest(individual_quest)

            return {
                "message": f"Successfully saved weekly quest list with {len(individual_quests)} individual quests",
                "quest_id": quest_id,
                "individual_quest_count": len(individual_quests),
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
        """Update individual quests with detailed homework information from HomeworkAgent."""
        try:
            print(f"DEBUG: Updating weekly quest with homework_data: {homework_data}")

            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                raise Exception(f"No weekly quest found for student {student_id} and period {period_id}")

            quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id

            print(f"DEBUG: Found existing weekly quest: {quest_id}")

            # Get all individual quests for this weekly quest
            individual_quests = self.individual_quest_dao.get_quests_by_quest_id(quest_id)
            quests_by_week = {q['week']: q for q in individual_quests}

            print(f"DEBUG: Found {len(individual_quests)} individual quests")

            homework_by_week = {}
            for quest_data in homework_data.get("list_of_quests", []):
                week = quest_data.get("Week", 1)
                homework_by_week[week] = quest_data

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
                        }
                    )
                    updated_count += 1
                    print(f"DEBUG: Updated individual quest {existing['individual_quest_id']} for week {week}")
                else:
                    # Create a new individual quest if none exists for this week
                    individual_quest = IndividualQuest(
                        individual_quest_id=str(uuid.uuid4()),
                        quest_id=quest_id,
                        student_id=student_id,
                        period_id=period_id,
                        description=homework_quest.get("Name", ""),
                        skills=homework_quest.get("Skills", ""),
                        week=week,
                        instructions=homework_quest.get("instructions", ""),
                        rubric=homework_quest.get("rubric", {}),
                        status="not_started"
                    )
                    self.individual_quest_dao.add_individual_quest(individual_quest)
                    updated_count += 1
                    print(f"DEBUG: Created new individual quest for week {week}")

            return {
                "message": f"Successfully updated {updated_count} quests",
                "quest_id": quest_id,
                "updated_quests_count": updated_count,
                "total_quests": len(individual_quests)
            }

        except Exception as e:
            print(f"Error updating weekly quest with homework: {str(e)}")
            raise Exception(f"Failed to update weekly quest: {str(e)}")

    def get_weekly_quests_for_student(self, student_id: str, period_id: str):
        """Get the weekly quest for a student in a specific period."""
        return self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)

    def get_individual_quests_for_student(self, student_id: str) -> list:
        """Get all individual quests for a student."""
        return self.individual_quest_dao.get_quests_by_student(student_id)

    def get_individual_quests_for_student_and_period(self, student_id: str, period_id: str) -> list:
        return self.individual_quest_dao.get_quests_by_student_and_period(student_id, period_id)

    def update_individual_quest_status(self, quest_id: str, individual_quest_id: str, status: str) -> dict:
        """Update the status of a specific individual quest."""
        try:
            self.individual_quest_dao.update_individual_quest(
                individual_quest_id,
                {"status": status}
            )

            return {
                "message": f"Successfully updated individual quest {individual_quest_id} status to {status}",
                "quest_id": quest_id,
                "individual_quest_id": individual_quest_id,
                "status": status
            }

        except Exception as e:
            print(f"Error updating individual quest status: {str(e)}")
            raise Exception(f"Failed to update quest status: {str(e)}")

    def get_individual_quest_by_id(self, quest_id: str, individual_quest_id: str):
        """Get a specific individual quest by its ID."""
        return self.individual_quest_dao.get_individual_quest_by_id(individual_quest_id)

    def verify_quest_structure(self, student_id: str, period_id: str) -> dict:
        """Verify that quests are saved correctly in both tables."""
        try:
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)
            if not weekly_quest:
                return {"error": "No weekly quest found"}

            quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id
            individual_quests = self.individual_quest_dao.get_quests_by_quest_id(quest_id)

            verification = {
                "weekly_quest": {
                    "quest_id": quest_id,
                    "student_id": student_id,
                    "period_id": period_id,
                },
                "individual_quests": {
                    "total_count": len(individual_quests),
                    "quest_id": quest_id,
                    "individual_quest_ids": [q["individual_quest_id"] for q in individual_quests],
                    "weeks": [q["week"] for q in individual_quests]
                },
                "verification": {
                    "individual_quest_count": len(individual_quests),
                    "all_share_same_quest_id": all(q["quest_id"] == quest_id for q in individual_quests),
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

            quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id
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

    def update_quests_preserving_completed_data(self, schedule_data: dict, homework_data: dict, student_id: str, period_id: str) -> dict:
        """
        Safely update quests while preserving completed quest data (grades, feedback, status).
        This method is designed for use when recommended changes trigger quest updates.
        """
        try:
            print(f"DEBUG: Starting safe quest update preserving completed data")

            # Get existing quests
            existing_quests = self.get_individual_quests_for_student_and_period(student_id, period_id)
            existing_by_week = {quest['week']: quest for quest in existing_quests}

            print(f"DEBUG: Found {len(existing_quests)} existing quests")

            # Get weekly quest
            weekly_quest = self.weekly_quest_dao.get_weekly_quest_by_student_and_period(student_id, period_id)

            if not weekly_quest and existing_quests:
                # Create a weekly quest row from existing individual quests
                print("DEBUG: No weekly quest found but individual quests exist - creating weekly quest row")
                quest_id = existing_quests[0]['quest_id']
                wq = WeeklyQuest(
                    quest_id=quest_id,
                    student_id=student_id,
                    period_id=period_id,
                )
                self.weekly_quest_dao.add_weekly_quest(wq)
                weekly_quest = {'quest_id': quest_id}
                print(f"DEBUG: Created weekly quest row with quest_id={quest_id}")

            elif not weekly_quest:
                # No weekly quest and no individual quests — create fresh
                print("DEBUG: No existing weekly quest or individual quests found, creating new structure")
                schedule_result = self.save_schedule_to_weekly_quests(schedule_data, student_id, period_id)
                homework_result = self.update_weekly_quest_with_homework(homework_data, student_id, period_id)
                return {
                    "message": "Created new quest structure",
                    "schedule_result": schedule_result,
                    "homework_result": homework_result,
                    "preserved_quests": 0,
                    "updated_quests": 0,
                    "created_quests": len(schedule_data.get("list_of_quests", [])),
                    "total_quests": len(schedule_data.get("list_of_quests", []))
                }

            quest_id = weekly_quest['quest_id'] if isinstance(weekly_quest, dict) else weekly_quest.quest_id

            # Process homework data by week for easier lookup
            homework_by_week = {}
            for quest_data in homework_data.get("list_of_quests", []):
                week = quest_data.get("Week", 1)
                homework_by_week[week] = quest_data

            # Update quests preserving completed data
            updated_count = 0
            preserved_count = 0
            created_count = 0

            for quest_data in schedule_data.get("list_of_quests", []):
                week = quest_data.get("Week", 1)
                existing_quest = existing_by_week.get(week)
                homework_quest = homework_by_week.get(week, {})

                if existing_quest:
                    has_grade = existing_quest.get('grade') is not None
                    is_completed = existing_quest.get('status') == 'completed'
                    is_in_progress = existing_quest.get('status') == 'in_progress'

                    if has_grade or is_completed or is_in_progress:
                        # Preserve completed/graded/in-progress quest data
                        print(f"DEBUG: Preserving completed data for week {week} quest {existing_quest['individual_quest_id']}")

                        updates = {}
                        new_skills = quest_data.get("Skills", existing_quest.get('skills', ''))
                        if new_skills != existing_quest.get('skills', ''):
                            updates['skills'] = new_skills

                        if updates:
                            self.individual_quest_dao.update_individual_quest(
                                existing_quest['individual_quest_id'],
                                updates
                            )

                        preserved_count += 1
                    else:
                        # Quest not yet completed — safe to update
                        print(f"DEBUG: Updating incomplete quest for week {week}")
                        self.individual_quest_dao.update_individual_quest(
                            existing_quest['individual_quest_id'],
                            {
                                "description": homework_quest.get("Name", quest_data.get("Name", "")),
                                "skills": quest_data.get("Skills", ""),
                                "instructions": homework_quest.get("instructions", ""),
                                "rubric": homework_quest.get("rubric", {})
                            }
                        )
                        updated_count += 1
                else:
                    # New quest — create it
                    print(f"DEBUG: Creating new quest for week {week}")
                    individual_quest = IndividualQuest(
                        individual_quest_id=str(uuid.uuid4()),
                        quest_id=quest_id,
                        student_id=student_id,
                        period_id=period_id,
                        description=homework_quest.get("Name", quest_data.get("Name", "")),
                        skills=quest_data.get("Skills", ""),
                        week=week,
                        instructions=homework_quest.get("instructions", ""),
                        rubric=homework_quest.get("rubric", {}),
                        status="not_started"
                    )
                    self.individual_quest_dao.add_individual_quest(individual_quest)
                    created_count += 1

            # Update weekly quest timestamp
            self.weekly_quest_dao.update_weekly_quest(quest_id, {})

            total = len(self.get_individual_quests_for_student_and_period(student_id, period_id))
            return {
                "message": f"Successfully updated quests preserving completed data",
                "preserved_quests": preserved_count,
                "updated_quests": updated_count,
                "created_quests": created_count,
                "total_quests": total,
                "quest_id": quest_id
            }

        except Exception as e:
            print(f"Error updating quests while preserving data: {str(e)}")
            raise Exception(f"Failed to update quests safely: {str(e)}")

    @staticmethod
    def parse_grade_data(grade_str: str) -> dict:
        """
        Parse grade data from stored string format.
        Handles both new rubric-based grades and legacy simple grades.
        
        Args:
            grade_str: The grade string from the database
            
        Returns:
            dict: Parsed grade information with 'detailed_grade', 'overall_score', and 'display_grade'
        """
        if not grade_str:
            return {
                "detailed_grade": None,
                "overall_score": None,
                "display_grade": "Not graded"
            }
        
        try:
            # Try to parse as new JSON format
            grade_data = json.loads(grade_str)
            if isinstance(grade_data, dict) and "detailed_grade" in grade_data:
                return {
                    "detailed_grade": grade_data.get("detailed_grade"),
                    "overall_score": grade_data.get("overall_score", "Score not available"),
                    "display_grade": grade_data.get("overall_score", "Score not available")
                }
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Legacy format - simple grade string
        return {
            "detailed_grade": None,
            "overall_score": grade_str,
            "display_grade": grade_str
        }

    @staticmethod
    def format_grade_for_display(grade_str: str) -> str:
        """
        Format grade data for simple display purposes.
        
        Args:
            grade_str: The grade string from the database
            
        Returns:
            str: Formatted grade string for display
        """
        grade_data = QuestService.parse_grade_data(grade_str)
        return grade_data["display_grade"] 