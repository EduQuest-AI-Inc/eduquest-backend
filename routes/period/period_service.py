from typing import Dict, Any
from data_access.period_dao import PeriodDAO
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.conversation_dao import ConversationDAO
from models.conversation import Conversation
from assistants import ltg
from datetime import datetime, timezone

class PeriodService:

    def __init__(self):
        self.period_dao = PeriodDAO()
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.conversation_dao = ConversationDAO()

    def verify_period_id(self, period_id: str) -> Any:
        if not period_id:
            raise ValueError("Missing period ID")

        period_items = self.period_dao.get_period_by_id(period_id)

        if not period_items:
            raise LookupError("Invalid period ID")

        return period_items[0]

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

        # Fetch period info (optional, for validation or context)
        period_items = self.period_dao.get_period_by_id(period_id)
        if not period_items:
            raise LookupError("Invalid period ID")
        period = period_items
        ltg_assistant_id = period.get("ltg_assistant_id")

        # Start LTG conversation
        ltg_conversation = ltg(student, assistant_id=ltg_assistant_id)
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
        """
        Continue the LTG conversation using the ltg class.
        Args:
            auth_token (str): The user's authentication token.
            conversation_type (str): The type of conversation (should be 'longterm' or similar).
            thread_id (str): The thread ID for the conversation.
            message (str): The user's message to continue the conversation.
        Returns:
            dict: Assistant's reply and metadata.
        """

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

        # Get the assistant id from the period if available, else use default
        period_id = conversation.get('period_id')
        ltg_assistant_id = None
        if period_id:
            period_items = self.period_dao.get_period_by_id(period_id)
            if period_items:
                ltg_assistant_id = period_items.get('ltg_assistant_id')
        if not ltg_assistant_id:
            ltg_assistant_id = 'asst_1NnTwxp3tBgFWPp2sMjHU3Or' # Default assistant ID

        # Continue conversation
        conv = ltg(student, assistant_id=ltg_assistant_id)
        conv.thread_id = thread_id
        try:


            reply = conv.cont_conv(message)

            print(f"LTG Conversation continued: {reply}")

            return {"response": reply}
        except Exception as e:
            return {"error": str(e)}