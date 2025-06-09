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
        self.session_dao = SessionDAO()
        self.student_dao = StudentDAO()
        self.conversation_dao = ConversationDAO()
        self.period_dao = PeriodDAO()

    def start_profile_assistant(self, auth_token: str):
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
            initial_conversation = ini_conv(student)
            response = initial_conversation.initiate()
            if not response or 'response' not in response:
                raise Exception("Failed to initiate conversation")

            # Save conversation to DB
            conversation = Conversation(
                thread_id=response['thread_id'],
                user_id=user_id,
                role="student",
                conversation_type="profile",
            )
            self.conversation_dao.add_conversation(conversation)

            # Only return thread_id and response
            return {
                'thread_id': response['thread_id'],
                'response': response.get('response')
            }

    def continue_profile_assistant(self, auth_token, conversation_type, thread_id, message):
        """
        Continue the profile assistant conversation using ini_conv.
        Args:
            auth_token (str): The user's authentication token.
            conversation_type (str): The type of conversation (e.g., 'profile').
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
        student = self.student_dao.get_student_by_id(user_id)[0]
        if not student:
            raise Exception("Student not found")

        # Continue conversation
        conv = ini_conv(student, thread_id)

        try:
            reply, is_complete, updated_profile = conv.cont_conv(message)

            if is_complete:
                # If the profile is complete, update the student's profile status
                self.student_dao.update_student(user_id, updated_profile)

            # return {
            #     "thread_id": thread_id,
            #     "reply": reply,
            #     "profile_complete": is_complete
            # }
            return {
                "response": reply
            }
        
        except Exception as e:
            return {"error": str(e)}
