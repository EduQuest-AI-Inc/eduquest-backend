import uuid
from openai import OpenAI
import os
from dotenv import load_dotenv
from data_access.session_dao import SessionDAO
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.conversation_dao import ConversationDAO
from models.conversation import Conversation
from datetime import datetime, timezone
from assistants import ini_conv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ASSISTANT_ID = 'asst_bmsuvfNCaHJYmqTlnT52AzXE'  # initial conversation assistant

class ConversationService:
    def __init__(self):
        pass

    def start_profile_assistant(self, auth_token: str):
            # Validate session
            session_dao = SessionDAO()
            sessions = session_dao.get_sessions_by_auth_token(auth_token)
            if not sessions:
                raise Exception("Invalid auth token")
            user_id = sessions[0]['user_id']


            # Fetch student info
            student_dao = StudentDAO()
            student = student_dao.get_student_by_id(user_id)[0]
            if not student:
                raise Exception("Student not found")

            # Initialize conversation
            initial_conversation = ini_conv(student)
            response = initial_conversation.initiate()
            if not response or 'response' not in response:
                raise Exception("Failed to initiate conversation")

            # Save conversation to DB
            conversation_dao = ConversationDAO()
            now = datetime.now(timezone.utc).isoformat()
            conversation = Conversation(
                thread_id=response['thread_id'],
                user_id=user_id,
                role="student",
                conversation_type="profile",
                last_updated_at=now
            )
            conversation_dao.add_conversation(conversation)

            return response
