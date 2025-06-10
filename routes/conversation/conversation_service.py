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
from assistants import ini_conv, update

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ASSISTANT_ID_INITIAL = 'asst_bmsuvfNCaHJYmqTlnT52AzXE'  # initial conversation assistant
ASSISTANT_ID_UPDATE = 'asst_oQlKvMpoDPp80zEabjvUiflj'   # update assistant

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
        student = self.student_dao.get_student_by_id(user_id)[0]
        if not student:
            raise Exception("Student not found")

        # Initialize conversation
        if conversation_type == "profile":
            initial_conversation = ini_conv(student)
        elif conversation_type == "update":
            initial_conversation = update(
                assistant_id=ASSISTANT_ID_UPDATE,
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
        student = self.student_dao.get_student_by_id(user_id)[0]
        if not student:
            raise Exception("Student not found")

        # Continue conversation
        if conversation_type == "profile":
            conv = ini_conv(student, thread_id)
        elif conversation_type == "update":
            conv = update(
                assistant_id=ASSISTANT_ID_UPDATE,
                instructor=True,  # or False depending on who is continuing
                week=3,
                thread_id=thread_id
            )
        else:
            raise Exception("Invalid conversation type")

        try:
            if conversation_type == "profile":
                reply, is_complete, updated_profile = conv.cont_conv(message)
                if is_complete:
                    self.student_dao.update_student(user_id, updated_profile)
                return {
                    "response": reply
                }
            elif conversation_type == "update":
                reply = conv.cont_conv(message)
                return {
                    "response": reply
                }

        except Exception as e:
            return {"error": str(e)}
