import uuid
from openai import OpenAI
import os
from dotenv import load_dotenv
from data_access.session_dao import SessionDAO
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.conversation_dao import ConversationDAO
from data_access.teacher_dao import TeacherDAO
from models.conversation import Conversation
from datetime import datetime, timezone
from assistants import ini_conv
from assistants import update as UpdateAssistant

#creating a temp file

import tempfile
import json

def dict_to_temp_file(data: dict, suffix=".json") -> str:
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=suffix) as tmp:
        json.dump(data, tmp)
        return tmp.name

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ASSISTANT_ID_INITIAL = 'asst_bmsuvfNCaHJYmqTlnT52AzXE'  

class ConversationService:
    def __init__(self):
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.conversation_dao = ConversationDAO()
        self.teacher_dao = TeacherDAO()
        self.period_dao = PeriodDAO()

    def start_profile_assistant(self, auth_token: str, conversation_type: str = "profile"):
        # Validate session
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']

        # Fetch student info
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        # Initialize conversation
        if conversation_type == "profile":
            initial_conversation = ini_conv(student)
        elif conversation_type == "update":
            initial_conversation = UpdateAssistant(
                assistant_id=ASSISTANT_ID_INITIAL,
                instructor=True  # or False depending on user role
            )
        else:
            raise Exception("Invalid conversation type")

        response = initial_conversation.initiate()
        if not response or 'response' not in response:
            raise Exception("Failed to initiate conversation")

        # Save conversation to DB
        conversation = Conversation(
            thread_id=response['thread_id'],
            user_id=user_id,
            role="student",
            conversation_type=conversation_type,
        )
        self.conversation_dao.add_conversation(conversation)

        return {
            'thread_id': response['thread_id'],
            'response': response.get('response')
        }

    def continue_profile_assistant(self, auth_token, conversation_type, thread_id, message):
        # Validate session and get user_id
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']

        # Retrieve conversation
        conversation = self.conversation_dao.get_conversation_by_thread_user_conversation_type(
            thread_id, user_id, conversation_type
        )
        if not conversation:
            raise Exception("Conversation not found")

        # Fetch student info
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        # Continue conversation
        if conversation_type == "profile":
            conv = ini_conv(student, thread_id)
        elif conversation_type == "update":
            conv = UpdateAssistant(
                assistant_id=ASSISTANT_ID_INITIAL,
                instructor=True,  # or False depending on who is continuing
                week=3,
                thread_id=thread_id
            )
        else:
            raise Exception("Invalid conversation type")

        try:
            if conversation_type == "profile":
                reply, is_complete, updated_profile = conv.cont_conv(message)
                if is_complete and updated_profile:
                    self.student_dao.update_student(user_id, updated_profile)
                return {
                    "response": reply,
                    "profile_complete": is_complete
                }
            elif conversation_type == "update":
                reply = conv.cont_conv(message)
                return {
                    "response": reply
                }

        except Exception as e:
            print(f"Error in continue_profile_assistant: {str(e)}")
            raise Exception(f"Failed to continue conversation: {str(e)}")

    def start_update_assistant(self, auth_token: str, quests_file: str, is_instructor: bool, week: int = None,
                               submission_file: str = None, student_id: str = None, period_id: str = None):
        """
        Start the update assistant conversation.
        """
        # Validate session
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")

        session = sessions[0]
        user_id = session.get("user_id")
        role = session.get("role")

        if not user_id or not role:
            raise Exception("Session missing user_id or role")

        # Fetch user info
        user = self.teacher_dao.get_teacher_by_id(user_id) if role == "teacher" else self.student_dao.get_student_by_id(user_id)
        if not user:
            raise Exception(f"{role.capitalize()} not found")

        user_profile_dict = user
        print("DEBUG user_profile_dict:", user_profile_dict)

        # Validate period_id and get assistant ID
        if not period_id:
            raise Exception("period_id is required")
        
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception(f"Period with id {period_id} not found")
        
        update_assistant_id = period.get('update_assistant_id')
        if not update_assistant_id or update_assistant_id == "placeholder_update_assistant_id":
            raise Exception(f"Update assistant ID not configured for period {period_id}")
        
        print(f"Using assistant ID: {update_assistant_id}")

        # Load quest data
        quests_data = None
        if is_instructor:
            if not student_id:
                raise Exception("Instructor must provide a student_id to fetch quests")
            from routes.quest.quest_service import QuestService
            quests_data = QuestService().get_individual_quests_for_student(student_id)
            print(f"Fetched {len(quests_data)} quests for student {student_id}")
        else:
            try:
                quests_data = json.loads(quests_file)
                print("Loaded quests from JSON string")
            except (json.JSONDecodeError, TypeError) as e:
                raise Exception(f"Failed to parse quests JSON: {e}")

        # Start assistant
        update_conversation = UpdateAssistant(
            update_assistant_id,
            user_profile_dict,
            quests_data,
            is_instructor,
            week,
            submission_file
        )

        raw_response = update_conversation.initiate()
        if not raw_response:
            raise Exception("Failed to initiate update conversation")

        # Instructors get formatted response
        if is_instructor:
            try:
                response_json = json.loads(raw_response)
                raw_response = response_json.get('response') or f"""\
Response: {response_json.get('feedback', 'No feedback')}
Grade: {response_json.get('grade', 'N/A')}
Recommended Changes: {response_json.get('recommended_change', 'None')}"""
            except json.JSONDecodeError:
                pass  # leave raw_response as-is

        # Save grade/feedback if student
        if not is_instructor and week and student_id:
            try:
                response_data = json.loads(raw_response)
                grade, feedback = response_data.get('grade'), response_data.get('feedback')

                if grade is not None and feedback is not None:
                    from routes.quest.quest_service import QuestService
                    quests = QuestService().get_individual_quests_for_student(student_id)
                    target_quest = next(
                        (q for q in quests if q.get('week') == week and (not period_id or q.get('period_id') == period_id)),
                        None
                    )

                    if target_quest:
                        from data_access.individual_quest_dao import IndividualQuestDAO
                        IndividualQuestDAO().update_quest_grade_and_feedback(
                            target_quest['individual_quest_id'],
                            str(grade),
                            feedback
                        )
                        print(f"Saved grade {grade} and feedback for quest {target_quest['individual_quest_id']}")
                    else:
                        print(f"Warning: Quest not found for week {week}, period {period_id}")
                else:
                    print("Warning: Assistant response missing grade or feedback")

            except Exception as e:
                print(f"Error processing assistant response: {e}")

        # Save conversation
        self.conversation_dao.add_conversation(Conversation(
            thread_id=update_conversation.thread_id,
            user_id=student_id if role == "teacher" and student_id else user_id,
            role=role,
            conversation_type="update",
            period_id=period_id
        ))

        return {
            "thread_id": update_conversation.thread_id,
            "response": raw_response
        }


    def continue_update_assistant(self, auth_token: str, thread_id: str, message: str, student_id: str = None):
        """
        Continue the update assistant conversation.
        Args:
            auth_token (str): The user's authentication token.
            thread_id (str): The thread ID for the conversation.
            message (str): The user's message to continue the conversation.
            student_id (str, optional): The student ID if the user is a teacher.
        Returns:
            dict: Assistant's response.
        """
        # Validate session
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']
        role = sessions[0].get('role', 'student')

        # Use student_id if teacher, else use user_id
        target_user_id = student_id if (role == "teacher" and student_id) else user_id

        # Retrieve conversation
        conversation = self.conversation_dao.get_conversation_by_thread_user_conversation_type(
            thread_id, target_user_id, "update"
        )
        if not conversation:
            raise Exception("Conversation not found")

        # Fetch student info
        student = self.student_dao.get_student_by_id(target_user_id)
        if not student:
            raise Exception("Student not found")

        # Get assistant ID from conversation's period
        period_id = conversation.get('period_id')
        if not period_id:
            raise Exception("Conversation missing period_id")
        
        period = self.period_dao.get_period_by_id(period_id)
        if not period:
            raise Exception(f"Period with id {period_id} not found")
        
        update_assistant_id = period.get('update_assistant_id')
        if not update_assistant_id or update_assistant_id == "placeholder_update_assistant_id":
            raise Exception(f"Update assistant ID not configured for period {period_id}")
        
        print(f"Using assistant ID for continuation: {update_assistant_id}")

        # Get quest data for continuation
        quests_data = None
        if role == "teacher" and student_id:
            try:
                from routes.quest.quest_service import QuestService
                quest_service = QuestService()
                quests_data = quest_service.get_individual_quests_for_student(student_id)
                print(f"DEBUG: Fetched {len(quests_data)} quests for continuation")
            except Exception as quest_error:
                print(f"DEBUG: Error fetching quests for continuation: {quest_error}")
                # Continue without quest data if fetch fails
                quests_data = None

        # Continue conversation
        update_conv = UpdateAssistant(update_assistant_id, student, quests_data, role == "teacher", thread_id=thread_id)

        try:
            response = update_conv.cont_conv(message)
            
            if role == "teacher":
                try:
                    response_json = json.loads(response)
                    if 'response' in response_json:
                        response = response_json['response']
                except json.JSONDecodeError:
                    pass 
            
            return {
                "response": response
            }
        except Exception as e:
            print(f"Error in continue_update_assistant: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}