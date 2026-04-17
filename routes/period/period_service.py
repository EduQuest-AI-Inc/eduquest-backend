from typing import Dict, Any, List
import os
if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.period_dao import PeriodDAO
    from data_access.supabase.session_dao import SessionDAO
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.conversation_dao import ConversationDAO
    from data_access.supabase.enrollment_dao import EnrollmentDAO
    from data_access.supabase.period_schedule_dao import PeriodScheduleDAO
    from data_access.supabase.weekly_quest_dao import WeeklyQuestDAO
    from data_access.supabase.individual_quest_dao import IndividualQuestDAO
    from data_access.supabase.ltg_conversation_dao import LtgConversationDAO
else:
    from data_access.period_dao import PeriodDAO
    from data_access.session_dao import SessionDAO
    from data_access.student_dao import StudentDAO
    from data_access.conversation_dao import ConversationDAO
    from data_access.enrollment_dao import EnrollmentDAO
    from data_access.period_schedule_dao import PeriodScheduleDAO
    from data_access.weekly_quest_dao import WeeklyQuestDAO
    from data_access.individual_quest_dao import IndividualQuestDAO
from models.conversation import Conversation
from models.enrollment import Enrollment
from datetime import datetime, timezone
from EQ_agents.agent import HWAgent
from routes.conversation.ltg_service import (
    initiate_ltg_conversation as ltg_initiate,
    continue_ltg_conversation as ltg_continue,
)
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
        self.period_schedule_dao = PeriodScheduleDAO()
        self.weekly_quest_dao = WeeklyQuestDAO()
        self.individual_quest_dao = IndividualQuestDAO()
        self.ltg_conversation_dao = LtgConversationDAO()
        self.quest_service = QuestService()

    def get_my_periods(self, auth_token: str) -> List[Dict[str, Any]]:
        """
        Return the authenticated student's enrolled periods with course names
        and long-term goals.
        """
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        student_id = sessions[0]['user_id']

        enrollments = self.enrollment_dao.get_enrollments_by_student(student_id)
        period_ids = [e['period_id'] for e in enrollments]

        # Batch-fetch LTGs for this student
        ltg_rows = (
            self.student_dao.client
            .table('student_long_term_goal')
            .select('period_id, goal_text')
            .eq('student_id', student_id)
            .execute()
        )
        ltg_map = {r['period_id']: r['goal_text'] for r in (ltg_rows.data or [])}

        result = []
        for pid in period_ids:
            period = self.period_dao.get_period_by_id(pid)
            if not period:
                continue
            result.append({
                'period_id': pid,
                'course_name': period.get('course', pid),
                'long_term_goal': ltg_map.get(pid),
            })

        return result

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

        # Validate session and get student_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        student_id = sessions[0]['user_id']

        # Verify period exists
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise LookupError("Invalid period ID")
        
        # Verify student exists
        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            raise Exception("Student not found")

        # Check enrollment via the enrollment table (not student document)
        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(student_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]

        if period_id in enrolled_period_ids:
            raise ValueError(f"You are already enrolled in period {period_id}")

        # Create enrollment record in the enrollment table
        enrollment = Enrollment(
            period_id=period_id,
            student_id=student_id,
            semester="2024-spring"
        )
        self.enrollment_dao.add_enrollment(enrollment)
        print(f"Created enrollment record for student {student_id} in period {period_id}")

        # If this is a real period (not tutorial), clean up tutorial periods
        if period_id != TUTORIAL_PERIOD_ID:
            self._cleanup_tutorial_periods(student_id)

        return period

    def unenroll_from_period(self, auth_token: str, period_id: str) -> Dict[str, Any]:
        """
        Remove the authenticated student from a class and delete all
        student-scoped data tied to that period (enrollment row,
        LTG conversation, long-term goal, weekly & individual quests).

        Shared class resources (period, period_schedule) are untouched.
        """
        if not period_id:
            raise ValueError("Missing period ID")

        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        student_id = sessions[0]['user_id']

        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            raise Exception("Student not found")

        # Check enrollment via the enrollment table
        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(student_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]
        if period_id not in enrolled_period_ids:
            raise ValueError(f"You are not enrolled in period {period_id}")

        # 1. Delete the enrollment table row
        try:
            self.enrollment_dao.delete_enrollment(student_id, period_id)
            print(f"Deleted enrollment row for student {student_id} in period {period_id}")
        except Exception as e:
            print(f"Warning: could not delete enrollment row: {e}")

        updated_enrollments = [p for p in enrolled_period_ids if p != period_id]

        # 3. Clean up LTG conversation for this period
        conversation_id = self.ltg_conversation_dao.delete_conversation(student_id, period_id)

        if conversation_id:
            try:
                self.conversation_dao.delete_conversation(conversation_id)
                print(f"Deleted LTG conversation {conversation_id}")
            except Exception as e:
                print(f"Warning: could not delete conversation {conversation_id}: {e}")

        # 4. Remove long-term goal entry for this period
        period_obj = self.period_dao.get_period_by_id(period_id)
        period_name = period_obj.get('course', period_id) if period_obj else period_id
        long_term_goals = student.get('long_term_goal', {})
        if isinstance(long_term_goals, list):
            long_term_goals = {}
        goal_removed = False
        if period_name in long_term_goals:
            long_term_goals.pop(period_name)
            goal_removed = True
        if period_id in long_term_goals:
            long_term_goals.pop(period_id)
            goal_removed = True
        if goal_removed:
            self.student_dao.update_student(student_id, {'long_term_goal': long_term_goals})
            print(f"Removed long-term goal for period {period_id}")

        # 5. Delete weekly quests for this student+period
        weekly_quests = self.weekly_quest_dao.get_quests_by_student_and_period(student_id, period_id)
        for wq in weekly_quests:
            self.weekly_quest_dao.delete_weekly_quest(wq.quest_id)
            print(f"Deleted weekly quest {wq.quest_id}")

        # 6. Delete individual quests for this student+period
        individual_quests = self.individual_quest_dao.get_quests_by_student_and_period(student_id, period_id)
        for iq in individual_quests:
            self.individual_quest_dao.delete_individual_quest(iq['individual_quest_id'])
            print(f"Deleted individual quest {iq['individual_quest_id']}")

        return {
            "message": f"Successfully unenrolled from period {period_id}",
            "period_id": period_id,
            "remaining_enrollments": updated_enrollments,
        }

    def initiate_ltg_conversation(self, auth_token: str, period_id: str) -> Any:
        """
        Initiate or resume a long-term goal (LTG) conversation for a given period.
        
        Uses OpenAI Conversations API via OpenAIConversationsSession. Each student gets
        one conversation_id per class (period), persisted on student.ltg_conversation_ids.
        
        Args:
            auth_token (str): The user's authentication token.
            period_id (str): The period ID.
        Returns:
            dict: Information about the LTG conversation including conversation_id.
        """
        if not period_id:
            raise ValueError("Missing period ID")

        # Validate session and get student_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        student_id = sessions[0]['user_id']

        # Fetch student info
        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            raise Exception("Student not found")

        # Fetch period info for vector store
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise LookupError("Invalid period ID")
        
        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise Exception("Period does not have a vector store configured")

        # Check if student already has a conversation for this period
        existing_conversation_id = self.ltg_conversation_dao.get_conversation_id(student_id, period_id)

        if existing_conversation_id:
            # Resume existing conversation - return the conversation_id for frontend to continue
            print(f"Resuming existing LTG conversation: {existing_conversation_id}")
            return {
                "conversation_id": existing_conversation_id,
                "response": {
                    "message": "Welcome back! Let's continue working on your long-term goal."
                },
                "resumed": True
            }

        # Prepare student data for LTG initiation
        student_data = {
            "first_name": student.get("first_name", ""),
            "last_name": student.get("last_name", ""),
            "grade": student.get("grade", ""),
            "strength": student.get("strength", []),
            "weakness": student.get("weakness", []),
            "interest": student.get("interest", []),
            "learning_style": student.get("learning_style", [])
        }

        # Start new LTG conversation using Conversations API
        print(f"Starting new LTG conversation for student {student_id} in period {period_id}")
        try:
            result = ltg_initiate(
                vector_store_id=vector_store_id,
                student=student_data,
                conversation_id=None  # Create new conversation
            )
        except Exception:
            raise
        
        conversation_id = result.get("conversation_id")
        if not conversation_id:
            raise Exception("Failed to create LTG conversation - no conversation_id returned")
        
        # Persist conversation_id in ltg_conversation table
        self.ltg_conversation_dao.upsert_conversation(student_id, period_id, conversation_id)
        print(f"Saved conversation_id {conversation_id} for student {student_id}, period {period_id}")

        return {
            "conversation_id": conversation_id,
            "response": {
                "message": result.get("message", ""),
                "goal_1": result.get("goal_1"),
                "goal_2": result.get("goal_2"),
                "goal_3": result.get("goal_3"),
            },
            "resumed": False
        }

    def continue_ltg_conversation(self, auth_token: str, conversation_type: str, conversation_id: str, message: str, period_id: str = None) -> Any:
        """
        Continue an LTG conversation using OpenAI Conversations API.
        
        Args:
            auth_token (str): The user's authentication token.
            conversation_type (str): Type of conversation (expected "longterm").
            conversation_id (str): The OpenAI conversation ID.
            message (str): The user's message.
            period_id (str, optional): The period ID (used to look up vector store).
        Returns:
            dict: Response with message and goal_chosen flag.
        """
        print(f"\n=== Continuing LTG Conversation ===")
        print(f"Conversation ID: {conversation_id}")
        print(f"Message: {message}")
        
        # Validate session and get student_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            print("Error: Invalid auth token")
            raise Exception("Invalid auth token")
        student_id = sessions[0]['user_id']
        print(f"User ID: {student_id}")

        # Fetch student info
        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            print("Error: Student not found")
            raise Exception("Student not found")

        # Find the period_id from ltg_conversation table if not provided
        if not period_id:
            period_id = self.ltg_conversation_dao.find_period_for_conversation(student_id, conversation_id)
        
        if not period_id:
            print("Error: Could not determine period for conversation")
            raise Exception("Could not determine period for conversation")
        
        print(f"Period ID: {period_id}")

        # Get period for vector store
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception("Period not found")
        
        vector_store_id = period.get("vector_store_id")
        if not vector_store_id:
            raise Exception("Period does not have a vector store configured")

        # Continue conversation using Conversations API
        try:
            result = ltg_continue(
                vector_store_id=vector_store_id,
                conversation_id=conversation_id,
                user_message=message
            )
            
            reply = result.get("message", "")
            goal_chosen = result.get("goal_chosen", False)
            chosen_goal = result.get("chosen_goal")
            
            print(f"\nLTG Assistant Response:")
            print(f"Reply: {reply}")
            print(f"Goal chosen: {goal_chosen}")

            # If a goal was chosen, save it to the student's record
            if goal_chosen and chosen_goal:
                print(f"\nSaving goal:")
                print(f"Period ID: {period_id}")
                print(f"Goal: {chosen_goal}")
                self.student_dao.update_long_term_goal(student_id, period_id, chosen_goal)
                print("Goal saved successfully")
            else:
                print("No goal was chosen or reply was empty")

            return {
                "response": reply,
                "goal_chosen": goal_chosen
            }
        except Exception as e:
            print(f"\nError in continue_ltg_conversation: {str(e)}")
            return {"error": str(e)}

    # Note: start_schedules_agent has been removed.
    # Quest generation now uses period_schedule.quest_enabled_weeks directly in start_homework_agent.
    
    def start_homework_agent(self, student_id: str, period_id: str):
        """Generate quests for a student in a period. Auth/authz is handled by the route."""
        try:
            student = self.student_dao.get_student_by_id(student_id)
            if not student:
                raise Exception("Student not found")

            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                raise Exception("Period not found")

            period_schedule = self.period_schedule_dao.get_by_period_id(period_id)
            if not period_schedule:
                raise Exception("No period schedule found. Teacher must generate a schedule first.")

            quest_enabled_weeks = period_schedule.quest_enabled_weeks or []
            if not quest_enabled_weeks:
                raise Exception("No quest weeks enabled by teacher. Teacher must select which weeks have quests.")

            print(f"DEBUG: Quest enabled weeks: {quest_enabled_weeks}")

            schedule_json = period_schedule.schedule_json or {}
            schedule_weeks = schedule_json.get("weeks", [])

            if not schedule_weeks:
                raise Exception("Period schedule has no weeks data. Teacher must generate a schedule.")

            print(f"DEBUG: Total weeks in schedule: {len(schedule_weeks)}")

            schedule_quests = []
            for week_data in schedule_weeks:
                week_num = week_data.get("week_number")
                if week_num in quest_enabled_weeks:
                    lessons = week_data.get("lessons", [])
                    skills = week_data.get("skills", [])
                    quest_name = f"Week {week_num}: " + "; ".join(lessons[:3]) if lessons else f"Week {week_num} Quest"
                    quest_skills = "; ".join(skills) if skills else "Practice skills from this week"
                    schedule_quests.append({"Name": quest_name, "Skills": quest_skills, "Week": week_num})
                    print(f"DEBUG: Added quest for week {week_num}")

            if not schedule_quests:
                raise Exception("No quests could be built from enabled weeks. Check period schedule data.")

            print(f"DEBUG: Building {len(schedule_quests)} quests for enabled weeks")

            conversation_id = self.ltg_conversation_dao.get_conversation_id(student_id, period_id)
            if not conversation_id:
                raise Exception(
                    "No LTG conversation found for this period. "
                    "Student must complete the Long-Term Goal conversation before generating quests."
                )

            print(f"DEBUG: Using conversation_id for HWAgent memory: {conversation_id}")

            existing_weekly_quest = self.quest_service.get_weekly_quests_for_student(student_id, period_id)
            if not existing_weekly_quest:
                print("DEBUG: No existing weekly quest, creating placeholders")
                schedule_dict = {"list_of_quests": schedule_quests}
                self.quest_service.save_schedule_to_weekly_quests(schedule_dict, student_id, period_id)

            print(f"DEBUG: Running HWAgent for {len(schedule_quests)} quests with conversation memory")
            homework_agent = HWAgent(student, period, schedule_quests, conversation_id=conversation_id)
            homework = homework_agent.run()

            print(f"Homework type: {type(homework)}")
            print(f"Homework content: {homework}")

            if isinstance(homework, list):
                homework_dict = {"list_of_quests": []}
                for quest in homework:
                    if hasattr(quest, 'model_dump'):
                        homework_dict["list_of_quests"].append(quest.model_dump())
                    elif isinstance(quest, dict):
                        homework_dict["list_of_quests"].append(quest)
                    else:
                        homework_dict["list_of_quests"].append({
                            "Name": getattr(quest, 'Name', ''),
                            "Skills": getattr(quest, 'Skills', ''),
                            "Week": getattr(quest, 'Week', 1),
                            "instructions": getattr(quest, 'instructions', ''),
                            "rubric": getattr(quest, 'rubric', {})
                        })
            elif hasattr(homework, 'model_dump'):
                homework_dict = homework.model_dump()
            elif isinstance(homework, dict):
                homework_dict = homework
            else:
                raise Exception(f"Invalid homework format: {type(homework)}")

            print(f"DEBUG: Homework quests count: {len(homework_dict.get('list_of_quests', []))}")

            save_result = self.quest_service.update_weekly_quest_with_homework(homework_dict, student_id, period_id)

            individual_quests = self.quest_service.get_individual_quests_for_student_and_period(student_id, period_id)
            if not individual_quests:
                print("DEBUG: No individual quests found, creating them from homework data")
                create_result = self.quest_service.create_individual_quests_from_homework(homework_dict, student_id, period_id)
                print(f"DEBUG: Created individual quests: {create_result}")

            return {
                "homework": homework_dict,
                "message": f"Homework generated successfully for {len(schedule_quests)} quest weeks",
                "saved_quests": save_result,
                "quest_weeks": quest_enabled_weeks
            }
        except Exception as e:
            print(f"Error in start_homework_agent: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to generate homework: {str(e)}")

    def update_quests_with_recommended_change(self, student_id: str, period_id: str, recommended_change: str):
        """
        Update student quests based on recommended changes from the update assistant.
        Re-generates homework (instructions + rubric) for incomplete quests only,
        preserving completed/graded quests. Auth/authz is handled by the caller.
        """
        try:
            print(f"DEBUG: Starting targeted quest update with recommended change: {recommended_change}")

            student = self.student_dao.get_student_by_id(student_id)
            if not student:
                raise Exception(f"Student not found: {student_id}")
            
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                raise Exception("Period not found")

            # Get existing quests
            existing_quests = self.quest_service.get_individual_quests_for_student_and_period(student_id, period_id)
            if not existing_quests:
                raise Exception("No existing quests found. Cannot update without existing quest structure.")
            
            print(f"DEBUG: Found {len(existing_quests)} existing quests")

            # Identify incomplete quests that can be updated
            incomplete_quests = []
            for quest in existing_quests:
                has_grade = quest.get('grade') is not None
                is_completed = quest.get('status') == 'completed'
                
                if not has_grade and not is_completed:
                    incomplete_quests.append({
                        "Name": quest.get('description', ''),
                        "Skills": quest.get('skills', ''),
                        "Week": quest.get('week', 1)
                    })
                    print(f"DEBUG: Week {quest.get('week')} quest is incomplete, can be updated")
                else:
                    print(f"DEBUG: Week {quest.get('week')} quest is completed/graded, preserving")
            
            if not incomplete_quests:
                print("DEBUG: No incomplete quests to update")
                return {
                    "message": "No incomplete quests to update - all quests are completed or graded",
                    "recommended_change": recommended_change,
                    "affected_quests": 0,
                    "preserved_quests": len(existing_quests),
                    "updated_quests": 0,
                    "total_quests": len(existing_quests)
                }
            
            print(f"DEBUG: {len(incomplete_quests)} incomplete quests can be updated")
            
            # Get conversation_id for HWAgent memory
            conversation_id = self.ltg_conversation_dao.get_conversation_id(student_id, period_id)
            
            if not conversation_id:
                print("WARNING: No conversation_id found, HWAgent will run without conversation memory")
            else:
                print(f"DEBUG: Using conversation_id for HWAgent memory: {conversation_id}")
            
            # Re-run HWAgent for incomplete quests with recommended change context
            # The recommended change is added to student context for HWAgent to consider
            student_with_context = dict(student)
            student_with_context['recommended_change'] = recommended_change
            
            homework_agent = HWAgent(
                student_with_context, 
                period, 
                incomplete_quests,
                conversation_id=conversation_id
            )
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
            
            print(f"DEBUG: Generated updated homework for {len(homework_dict.get('list_of_quests', []))} quests")
            
            # Update the weekly quest with the new homework
            update_result = self.quest_service.update_weekly_quest_with_homework(
                homework_dict,
                student_id,
                period_id
            )
            
            print(f"DEBUG: Quest update completed: {update_result.get('message', 'No message')}")
            
            affected_weeks = [q.get("Week") for q in incomplete_quests]
            return {
                "message": f"Successfully updated {len(incomplete_quests)} incomplete quests based on recommended changes",
                "recommended_change": recommended_change,
                "affected_weeks": affected_weeks,
                "quest_update_details": update_result,
                "affected_quests": len(incomplete_quests),
                "preserved_quests": len(existing_quests) - len(incomplete_quests),
                "updated_quests": len(incomplete_quests),
                "total_quests": len(existing_quests)
            }
            
        except Exception as e:
            print(f"Error in update_quests_with_recommended_change: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to update quests with recommended change: {str(e)}")

    # Note: start_schedules_agent_with_changes has been removed.
    # Quest generation now uses period_schedule.quest_enabled_weeks directly.

    def _cleanup_tutorial_periods(self, student_id: str):
        """Remove tutorial periods when student adds their first real period"""
        existing_enrollments = self.enrollment_dao.get_enrollments_by_student(student_id)
        enrolled_period_ids = [e['period_id'] for e in existing_enrollments]

        if TUTORIAL_PERIOD_ID in enrolled_period_ids:
            self._remove_tutorial_enrollment(student_id)
            print(f"Cleaned up tutorial period for student {student_id}")

    def _remove_tutorial_enrollment(self, student_id: str):
        """Remove tutorial enrollment record"""
        try:
            self.enrollment_dao.delete_enrollment(student_id, TUTORIAL_PERIOD_ID)
            print(f"Removed tutorial enrollment for student {student_id}")
        except Exception as e:
            print(f"Error removing tutorial enrollment: {e}")

