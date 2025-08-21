from typing import Dict, Any
from data_access.period_dao import PeriodDAO
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.conversation_dao import ConversationDAO
from data_access.enrollment_dao import EnrollmentDAO
from models.conversation import Conversation
from models.enrollment import Enrollment
from assistants import ltg
from datetime import datetime, timezone
from EQ_agents.agent import SchedulesAgent, HWAgent
from routes.quest.quest_service import QuestService

# Tutorial period constant
TUTORIAL_PERIOD_ID = "PRECALC-58F9-88F5"

class PeriodService:

    def __init__(self):
        self.period_dao = PeriodDAO()
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.conversation_dao = ConversationDAO()
        self.enrollment_dao = EnrollmentDAO()
        self.quest_service = QuestService()

    def verify_period_id(self, auth_token: str, period_id: str) -> Any:
        """
        Verify a period ID and add it to the student's enrollments if valid.
        
        Args:
            auth_token: The user's authentication token
            period_id: The period ID to verify
        Returns:
            dict: The period information if valid
        """
        if not period_id:
            raise ValueError("Missing period ID")

        # Validate session and get user_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']

        # Verify period exists
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise LookupError("Invalid period ID")
        
        # Get current student data
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")
            
        # Get current enrollments or initialize empty list
        current_enrollments = student.get('enrollments', [])
        
        # Check if student is already enrolled in this period
        if period_id in current_enrollments:
            raise ValueError(f"You are already enrolled in period {period_id}")
        
        # Add period to enrollments
        current_enrollments.append(period_id)
        # Update student record with new enrollments
        self.student_dao.update_student(user_id, {'enrollments': current_enrollments})
        print(f"Added period {period_id} to student {user_id}'s enrollments")

        # Create enrollment record
        enrollment = Enrollment(
            period_id=period_id,
            student_id=user_id,
            semester="2024-spring"  # You might want to make this configurable
        )
        self.enrollment_dao.add_enrollment(enrollment)
        print(f"Created enrollment record for student {user_id} in period {period_id}")

        # If this is a real period (not tutorial), clean up tutorial periods
        if period_id != TUTORIAL_PERIOD_ID:
            self._cleanup_tutorial_periods(user_id)

        return period

    def initiate_ltg_conversation(self, auth_token: str, period_id: str) -> Any:
        """
        Initiate a long-term goal (LTG) conversation for a given period.
        Args:
            auth_token (str): The user's authentication token.
            period_id (str): The period ID.
        Returns:
            dict: Information about the LTG conversation.
        """
        if not period_id:
            raise ValueError("Missing period ID")

        # Validate session and get user_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']

        # Fetch student info
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        # Ensure student data has all required fields
        student_data = {
            "first_name": student.get("first_name", ""),
            "last_name": student.get("last_name", ""),
            "grade": student.get("grade", ""),
            "strength": student.get("strength", []),
            "weakness": student.get("weakness", []),
            "interest": student.get("interest", []),
            "learning_style": student.get("learning_style", [])
        }

        # Fetch period info (optional, for validation or context)
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise LookupError("Invalid period ID")
        
        ltg_assistant_id = period.get("ltg_assistant_id")
        if not ltg_assistant_id:
            ltg_assistant_id = 'asst_1NnTwxp3tBgFWPp2sMjHU3Or'  # Default assistant ID

        # Start LTG conversation
        ltg_conversation = ltg(student_data, assistant_id=ltg_assistant_id)
        response = ltg_conversation.initiate()

        thread_id = response.get('thread_id')

        # Save conversation to DB
        conversation = Conversation(
            thread_id=thread_id,
            user_id=user_id,
            role="student",
            conversation_type="longterm",
            created_at=datetime.now(timezone.utc).isoformat(),
            period_id=period_id
        )
        self.conversation_dao.add_conversation(conversation)

        return {
            "thread_id": thread_id,
            "response": response
        }

    def continue_ltg_conversation(self, auth_token: str, conversation_type: str, thread_id: str, message: str) -> Any:
        print(f"\n=== Starting LTG Conversation ===")
        print(f"Thread ID: {thread_id}")
        print(f"Message: {message}")
        
        # Validate session and get user_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            print("Error: Invalid auth token")
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']
        print(f"User ID: {user_id}")

        # Retrieve conversation
        conversation = self.conversation_dao.get_conversation_by_thread_user_conversation_type(
            thread_id, user_id, conversation_type
        )
        if not conversation:
            print("Error: Conversation not found")
            raise Exception("Conversation not found")
        print(f"Found conversation: {conversation}")

        # Fetch student info
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            print("Error: Student not found")
            raise Exception("Student not found")
        print(f"Found student: {student}")

        # Get the assistant id from the period if available, else use default
        period_id = conversation.get('period_id')
        print(f"Period ID: {period_id}")
        
        ltg_assistant_id = None
        if period_id:
            period_items = self.period_dao.get_period_by_id(period_id)
            if period_items:
                ltg_assistant_id = period_items.get('ltg_assistant_id')
        if not ltg_assistant_id:
            ltg_assistant_id = 'asst_1NnTwxp3tBgFWPp2sMjHU3Or' # Default assistant ID
        print(f"Using assistant ID: {ltg_assistant_id}")

        # Continue conversation
        conv = ltg(student, assistant_id=ltg_assistant_id)
        conv.thread_id = thread_id
        try:
            reply, goal_chosen = conv.cont_conv(message)
            print(f"\nLTG Assistant Response:")
            print(f"Reply: {reply}")
            print(f"Goal chosen: {goal_chosen}")

            # If a goal was chosen, save it to the student's record
            if goal_chosen and reply:
                # Get the period name from the period record
                period_data = self.period_dao.get_period_by_id(period_id)
                if period_data:
                    # Use course name as period name, fallback to period_id
                    period_name = period_data.get('course', period_id)
                    print(f"\nSaving goal:")
                    print(f"Period: {period_name}")
                    print(f"Goal: {reply}")
                    # Update the student's long-term goal for this period
                    self.student_dao.update_long_term_goal(user_id, period_name, reply)
                    print("Goal saved successfully")
                else:
                    print(f"Warning: Could not find period with ID {period_id}")
            else:
                print("No goal was chosen or reply was empty")

            return {
                "response": reply,
                "goal_chosen": goal_chosen
            }
        except Exception as e:
            print(f"\nError in continue_ltg_conversation: {str(e)}")
            return {"error": str(e)}
        
    def start_schedules_agent(self, auth_token: str, period_id: str):
        try:
            sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
            if not sessions:
                raise Exception("Invalid auth token")
            user_id = sessions[0]['user_id']

            student = self.student_dao.get_student_by_id(user_id)
            if not student:
                raise Exception("Student not found")
            
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                raise Exception("Period not found")

            schedules_agent = SchedulesAgent(student, period)
            schedule = schedules_agent.run()
            print(schedule)
            print(type(schedule))
            print(schedule.model_dump_json())
            
            # Save schedule to database
            schedule_dict = schedule.model_dump()
            save_result = self.quest_service.save_schedule_to_weekly_quests(schedule_dict, user_id, period_id)
            
            return {
                "schedule": schedule_dict,
                "message": "Schedule generated and saved successfully",
                "saved_quests": save_result
            }
        except Exception as e:
            print(f"Error in start_schedules_agent: {str(e)}")
            raise Exception(f"Failed to generate schedule: {str(e)}")
    
    def start_homework_agent(self, auth_token: str, period_id: str):
        try:
            sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
            if not sessions:
                raise Exception("Invalid auth token")
            user_id = sessions[0]['user_id']
            
            student = self.student_dao.get_student_by_id(user_id)
            if not student:
                raise Exception("Student not found")
            
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                raise Exception("Period not found")
            
            # Get the existing schedule from the weekly quest table
            print(f"DEBUG: Looking for weekly quest for user_id={user_id}, period_id={period_id}")
            weekly_quest = self.quest_service.get_weekly_quests_for_student(user_id, period_id)
            if not weekly_quest:
                raise Exception("No weekly quest found. Please run the schedules agent first.")
            
            print(f"DEBUG: Found weekly quest with {len(weekly_quest.quests)} quests")
            
            # Convert weekly quest to schedule format for homework agent
            schedule_quests = []
            for quest_item in weekly_quest.quests:
                schedule_quests.append({
                    "Name": quest_item.name,
                    "Skills": quest_item.skills,
                    "Week": quest_item.week
                })
            
            # schedule_dict = {"list_of_quests": schedule_quests}
            # print(f"DEBUG: Schedule dict for homework agent: {schedule_dict}")
            
            # Use improved HWAgent with timeout and error handling
            homework_agent = HWAgent(
                student, 
                period, 
                schedule_quests
            )
            homework = homework_agent.run()
            
            print(f"Homework type: {type(homework)}")
            print(f"Homework content: {homework}")
            
            # Handle list of IndividualQuest objects
            if isinstance(homework, list):
                # Convert list of IndividualQuest objects to the expected dict format
                homework_dict = {
                    "list_of_quests": []
                }
                for quest in homework:
                    if hasattr(quest, 'model_dump'):
                        homework_dict["list_of_quests"].append(quest.model_dump())
                    elif isinstance(quest, dict):
                        homework_dict["list_of_quests"].append(quest)
                    else:
                        # Try to convert to dict manually if it's an IndividualQuest object
                        quest_dict = {
                            "Name": getattr(quest, 'Name', ''),
                            "Skills": getattr(quest, 'Skills', ''),
                            "Week": getattr(quest, 'Week', 1),
                            "instructions": getattr(quest, 'instructions', ''),
                            "rubric": getattr(quest, 'rubric', {})
                        }
                        homework_dict["list_of_quests"].append(quest_dict)
            elif hasattr(homework, 'model_dump'):
                homework_dict = homework.model_dump()
            elif isinstance(homework, dict):
                homework_dict = homework
            else:
                raise Exception(f"Invalid homework format: {type(homework)}")
            
            print(f"Homework dict: {homework_dict}")
            print(f"DEBUG: Homework quests count: {len(homework_dict.get('list_of_quests', []))}")
            
            # Update the weekly quest with detailed homework information
            save_result = self.quest_service.update_weekly_quest_with_homework(homework_dict, user_id, period_id)
            
            # Check if individual quests were created, if not create them
            individual_quests = self.quest_service.get_individual_quests_for_student_and_period(user_id, period_id)
            if not individual_quests:
                print("DEBUG: No individual quests found, creating them from homework data")
                create_result = self.quest_service.create_individual_quests_from_homework(homework_dict, user_id, period_id)
                print(f"DEBUG: Created individual quests: {create_result}")
            
            return {
                "homework": homework_dict,
                "message": "Homework generated and saved successfully",
                "saved_quests": save_result
            }
        except Exception as e:
            print(f"Error in start_homework_agent: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to generate homework: {str(e)}")

    def update_quests_with_recommended_change(self, auth_token: str, period_id: str, recommended_change: str, student_id: str = None):
        """
        Update student quests based on recommended changes from the update assistant.
        This method identifies which quests are affected by the recommended change
        and only updates those specific quests, preserving all other quest data.
        
        Args:
            auth_token: The user's authentication token
            period_id: The period ID for the student
            recommended_change: The recommended change text from the update assistant
            student_id: Optional student ID (used when teacher makes recommendations)
            
        Returns:
            dict: Results of the quest update process
        """
        try:
            print(f"DEBUG: Starting targeted quest update with recommended change: {recommended_change}")
            
            # Validate session and get user_id
            sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
            if not sessions:
                raise Exception("Invalid auth token")
            session_user_id = sessions[0]['user_id']
            session_role = sessions[0].get('role', 'student')

            # Determine the target student ID
            if student_id:
                # Teacher specifying a student to update
                target_student_id = student_id
                print(f"DEBUG: Teacher ({session_user_id}) updating quests for student {target_student_id}")
            else:
                # Student updating their own quests
                target_student_id = session_user_id
                print(f"DEBUG: Student ({session_user_id}) updating their own quests")

            student = self.student_dao.get_student_by_id(target_student_id)
            if not student:
                raise Exception(f"Student not found: {target_student_id}")
            
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                raise Exception("Period not found")

            # Get existing quests to understand current structure
            existing_quests = self.quest_service.get_individual_quests_for_student_and_period(target_student_id, period_id)
            if not existing_quests:
                raise Exception("No existing quests found. Cannot update without existing quest structure.")
            
            print(f"DEBUG: Found {len(existing_quests)} existing quests")

            # Step 1: Generate new schedule with recommended changes
            print("DEBUG: Generating new schedule with recommended changes...")
            schedules_agent = SchedulesAgent(student, period, recommended_change)
            new_schedule = schedules_agent.run()
            new_schedule_dict = new_schedule.model_dump()
            
            # Step 2: Compare schedules to identify affected quests
            print("DEBUG: Identifying which quests were affected by the recommended change...")
            existing_by_week = {quest['week']: quest for quest in existing_quests}
            affected_weeks = []
            
            for new_quest_data in new_schedule_dict.get("list_of_quests", []):
                week = new_quest_data.get("Week", 1)
                existing_quest = existing_by_week.get(week)
                
                if not existing_quest:
                    # New quest week - needs homework generation
                    affected_weeks.append(week)
                    print(f"DEBUG: Week {week} is new, needs homework generation")
                else:
                    # Check if quest details changed significantly
                    new_name = new_quest_data.get("Name", "")
                    new_skills = new_quest_data.get("Skills", "")
                    existing_name = existing_quest.get('description', '')
                    existing_skills = existing_quest.get('skills', '')
                    
                    # Consider quest affected if name or skills changed significantly
                    if new_name != existing_name or new_skills != existing_skills:
                        # Only update if quest is not completed/graded
                        has_grade = existing_quest.get('grade') is not None
                        is_completed = existing_quest.get('status') == 'completed'
                        
                        if not has_grade and not is_completed:
                            affected_weeks.append(week)
                            print(f"DEBUG: Week {week} quest changed and is incomplete, needs homework regeneration")
                        else:
                            print(f"DEBUG: Week {week} quest changed but is completed/graded, preserving existing data")
            
            if not affected_weeks:
                print("DEBUG: No quests need updating based on recommended change")
                return {
                    "message": "No quests need updating - recommended change does not affect any incomplete quests",
                    "recommended_change": recommended_change,
                    "affected_quests": 0,
                    "preserved_quests": len(existing_quests),
                    "updated_quests": 0,
                    "created_quests": 0,
                    "total_quests": len(existing_quests)
                }
            
            print(f"DEBUG: {len(affected_weeks)} quests need updating: weeks {affected_weeks}")
            
            # Step 3: Generate homework ONLY for affected quests
            print("DEBUG: Generating homework only for affected quests...")
            
            # Create a minimal schedule containing only affected quests
            affected_schedule_quests = []
            for new_quest_data in new_schedule_dict.get("list_of_quests", []):
                week = new_quest_data.get("Week", 1)
                if week in affected_weeks:
                    affected_schedule_quests.append({
                        "Name": new_quest_data.get("Name", ""),
                        "Skills": new_quest_data.get("Skills", ""),
                        "Week": week
                    })
            
            if affected_schedule_quests:
                # Generate homework only for the affected quests
                homework_agent = HWAgent(student, period, affected_schedule_quests)
                homework = homework_agent.run()
                
                # Convert homework to expected dict format
                if isinstance(homework, list):
                    homework_dict = {"list_of_quests": []}
                    for quest in homework:
                        if hasattr(quest, 'model_dump'):
                            homework_dict["list_of_quests"].append(quest.model_dump())
                        elif isinstance(quest, dict):
                            homework_dict["list_of_quests"].append(quest)
                        else:
                            quest_dict = {
                                "Name": getattr(quest, 'Name', ''),
                                "Skills": getattr(quest, 'Skills', ''),
                                "Week": getattr(quest, 'Week', 1),
                                "instructions": getattr(quest, 'instructions', ''),
                                "rubric": getattr(quest, 'rubric', {})
                            }
                            homework_dict["list_of_quests"].append(quest_dict)
                else:
                    homework_dict = homework if isinstance(homework, dict) else homework.model_dump()
                
                print(f"DEBUG: Generated homework for {len(homework_dict.get('list_of_quests', []))} affected quests")
            else:
                homework_dict = {"list_of_quests": []}
            
            # Step 4: Apply targeted updates preserving completed data
            print("DEBUG: Applying targeted updates while preserving completed data...")
            
            # Create a combined schedule that includes both unchanged and changed quests
            combined_schedule_dict = {"list_of_quests": []}
            
            # Add all quests from new schedule
            for new_quest_data in new_schedule_dict.get("list_of_quests", []):
                combined_schedule_dict["list_of_quests"].append(new_quest_data)
            
            # Use the targeted update method
            update_result = self.quest_service.update_quests_preserving_completed_data(
                combined_schedule_dict, 
                homework_dict, 
                target_student_id, 
                period_id
            )
            
            print(f"DEBUG: Targeted quest update completed: {update_result.get('message', 'No message')}")
            
            return {
                "message": f"Successfully updated {len(affected_weeks)} quests based on recommended changes while preserving completed work",
                "recommended_change": recommended_change,
                "affected_weeks": affected_weeks,
                "quest_update_details": update_result,
                "affected_quests": len(affected_weeks),
                "preserved_quests": update_result.get("preserved_quests", 0),
                "updated_quests": update_result.get("updated_quests", 0),
                "created_quests": update_result.get("created_quests", 0),
                "total_quests": update_result.get("total_quests", 0)
            }
            
        except Exception as e:
            print(f"Error in update_quests_with_recommended_change: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to update quests with recommended change: {str(e)}")

    def start_schedules_agent_with_changes(self, auth_token: str, period_id: str, recommended_change: str = None):
        """
        Start the schedules agent with optional recommended changes.
        
        Args:
            auth_token: The user's authentication token
            period_id: The period ID
            recommended_change: Optional recommended change text
            
        Returns:
            dict: Results of the schedule generation
        """
        try:
            sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
            if not sessions:
                raise Exception("Invalid auth token")
            user_id = sessions[0]['user_id']

            student = self.student_dao.get_student_by_id(user_id)
            if not student:
                raise Exception("Student not found")
            
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                raise Exception("Period not found")

            # Use the enhanced SchedulesAgent with recommended changes
            schedules_agent = SchedulesAgent(student, period, recommended_change)
            schedule = schedules_agent.run()
            print(schedule)
            print(type(schedule))
            print(schedule.model_dump_json())
            
            # Save schedule to database
            schedule_dict = schedule.model_dump()
            save_result = self.quest_service.save_schedule_to_weekly_quests(schedule_dict, user_id, period_id)
            
            change_message = f" with recommended changes: {recommended_change}" if recommended_change else ""
            
            return {
                "schedule": schedule_dict,
                "message": f"Schedule generated and saved successfully{change_message}",
                "saved_quests": save_result,
                "recommended_change_applied": bool(recommended_change)
            }
        except Exception as e:
            print(f"Error in start_schedules_agent_with_changes: {str(e)}")
            raise Exception(f"Failed to generate schedule with changes: {str(e)}")

    def _cleanup_tutorial_periods(self, student_id: str):
        """Remove tutorial periods when student adds their first real period"""
        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            return
        
        current_enrollments = student.get('enrollments', [])
        
        # Check if student has tutorial period enrolled
        if TUTORIAL_PERIOD_ID in current_enrollments:
            # Remove tutorial period from enrollments
            updated_enrollments = [p for p in current_enrollments if p != TUTORIAL_PERIOD_ID]
            self.student_dao.update_student(student_id, {'enrollments': updated_enrollments})
            
            # Remove tutorial enrollment record
            self._remove_tutorial_enrollment(student_id)
            
            print(f"Cleaned up tutorial period for student {student_id}")

    def _remove_tutorial_enrollment(self, student_id: str):
        """Remove tutorial enrollment record"""
        try:
            enrollments = self.enrollment_dao.get_enrollments_by_period(TUTORIAL_PERIOD_ID)
            for enrollment in enrollments:
                if enrollment.get('student_id') == student_id:
                    self.enrollment_dao.delete_enrollment(
                        TUTORIAL_PERIOD_ID, 
                        enrollment.get('enrolled_at')
                    )
                    print(f"Removed tutorial enrollment for student {student_id}")
                    break
        except Exception as e:
            print(f"Error removing tutorial enrollment: {e}")

