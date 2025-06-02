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

def start_conversation_service(auth_token: str, period_id: str):
    # Validate session
    session_dao = SessionDAO()
    sessions = session_dao.get_sessions_by_auth_token(auth_token)
    if not sessions:
        raise Exception("Invalid auth token")
    user_id = sessions[0]['user_id']

    # Fetch period info (optional, for context)
    period_dao = PeriodDAO()
    period_items = period_dao.get_period_by_id(period_id)
    if not period_items:
        raise Exception("Invalid period_id")
    period = period_items[0]

    initial_conversation_assistant_id = period['initial_conversation_assistant_id']

    # Fetch student info
    student_dao = StudentDAO()
    student = student_dao.get_student_by_id(user_id)[0]
    if not student:
        raise Exception("Student not found")

    # Initialize conversation
    initial_conversation = ini_conv(student, initial_conversation_assistant_id)
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
        conversation_type="initial",
        last_updated_at=now,
        period_id=period_id,
    )
    conversation_dao.add_conversation(conversation)

    return response
