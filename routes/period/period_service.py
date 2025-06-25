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

class PeriodService:

    def __init__(self):
        self.period_dao = PeriodDAO()
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.conversation_dao = ConversationDAO()
        self.enrollment_dao = EnrollmentDAO()

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
        
        # Add period to enrollments if not already enrolled
        if period_id not in current_enrollments:
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
            
            return {
                "schedule": schedule.model_dump(), #converts to dict because agent is returning a pydantic model object
                "message": "Schedule generated successfully"
        }
    
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
            
            schedules_agent = SchedulesAgent(student, period)
            schedule = schedules_agent.run()
            
            print(f"Schedule type: {type(schedule)}")
            print(f"Schedule content: {schedule}")
            
            if hasattr(schedule, 'model_dump'):
                schedule_dict = schedule.model_dump()
            elif isinstance(schedule, dict):
                schedule_dict = schedule
            else:
                raise Exception(f"Invalid schedule format: {type(schedule)}")
            
            print(f"Schedule dict: {schedule_dict}")
            
            homework_agent = HWAgent(student, period, schedule_dict)
            homework = homework_agent.run()
            
            print(f"Homework type: {type(homework)}")
            print(f"Homework content: {homework}")
            
            if hasattr(homework, 'model_dump'):
                homework_dict = homework.model_dump()
            elif isinstance(homework, dict):
                homework_dict = homework
            else:
                raise Exception(f"Invalid homework format: {type(homework)}")
            
            print(f"Homework dict: {homework_dict}")
            
            return {
                "homework": homework_dict,
                "message": "Homework generated successfully"
            }
        except Exception as e:
            print(f"Error in start_homework_agent: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to generate homework: {str(e)}")