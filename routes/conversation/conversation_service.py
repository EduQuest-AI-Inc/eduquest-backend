import uuid
from openai import OpenAI
import os
from dotenv import load_dotenv
from data_access.session_dao import SessionDAO
from data_access.period_dao import PeriodDAO
from data_access.conversation_dao import ConversationDAO
from models.conversation import Conversation
from datetime import datetime, timezone

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

    # Create a new thread id
    thread_id = str(uuid.uuid4())

    # Call OpenAI Assistant for initial message
    thread = client.beta.threads.create()
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )
    # Wait for run to complete (polling)
    import time
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status in ["completed", "failed", "cancelled"]:
            break
        time.sleep(1)
    if run_status.status != "completed":
        raise Exception("Assistant failed to generate response")

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    assistant_message = None
    for msg in reversed(messages.data):
        if msg.role == "assistant":
            assistant_message = msg.content[0].text.value
            break
    if not assistant_message:
        raise Exception("No assistant response found")

    # Save conversation to DB
    conversation_dao = ConversationDAO()
    now = datetime.now(timezone.utc).isoformat()
    conversation = Conversation(
        thread_id=thread_id,
        last_updated_at=now,
        user_id=user_id,
        period_id=period_id,
        messages=[
            {
                "role": "assistant",
                "message": assistant_message,
                "timestamp": now
            }
        ]
    )
    conversation_dao.add_conversation(conversation)

    return {
        "thread_id": thread_id,
        "assistant_message": assistant_message
    }
