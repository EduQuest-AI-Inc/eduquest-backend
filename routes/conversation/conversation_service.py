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
# def generate_mock_quests_file():
#     mock_quests = [
#         {
#             "week": 1,
#             "quest_name": "Explore Fractions",
#             "description": "Use objects at home to show 1/2, 1/4, and 1/3. Take a photo.",
#             "skills_covered": "Fractions, Visual Math",
#             "skills_mastered": "Understanding Part-Whole Relationships"
#         },
#         {
#             "week": 2,
#             "quest_name": "Math in Recipes",
#             "description": "Double or halve a recipe. Submit the modified version and a reflection.",
#             "skills_covered": "Multiplication, Division",
#             "skills_mastered": "Applying Math to Real Life"
#         }
#     ]
#
#     temp = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".json")
#     json.dump(mock_quests, temp, indent=2)
#     temp.close()
#     return temp.name  # for testing only

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
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        # Initialize conversation
        if conversation_type == "profile":
            initial_conversation = ini_conv(student)
        elif conversation_type == "update":
            initial_conversation = UpdateAssistant(
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
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        # Continue conversation
        if conversation_type == "profile":
            conv = ini_conv(student, thread_id)
        elif conversation_type == "update":
            conv = UpdateAssistant(
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
                               submission_file: str = None):
        """
        Start the update assistant conversation.

        Args:
            auth_token (str): The user's authentication token.
            quests_file (str): Path to the quests file.
            is_instructor (bool): Whether the user is an instructor.
            week (int, optional): Week number for student submissions.
            submission_file (str, optional): Path to the submission file for students.

        Returns:
            dict: Assistant's response and thread ID.
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

        # Fetch user info based on role
        if role == "teacher":
            user = self.teacher_dao.get_teacher_by_id(user_id)
        elif role == "student":
            user = self.student_dao.get_student_by_id(user_id)
        else:
            raise Exception(f"Unrecognized role: {role}")

        if not user:
            raise Exception(f"{role.capitalize()} not found")

        user_profile_dict = user
        student_file = dict_to_temp_file(user_profile_dict)
        print("DEBUG user_profile_dict:", user_profile_dict)

        student_record = user_profile_dict
        quests = student_record['quests']['pre_calc']
        quests_file = dict_to_temp_file(quests)

        # Initialize update conversation
        update_conversation = UpdateAssistant(
            ASSISTANT_ID_UPDATE,
            student_file,
            quests_file,
            is_instructor,
            week,
            submission_file
        )

        raw_response = update_conversation.initiate()
        print("Raw response from update_conversation.initiate():", raw_response)

        if not raw_response:
            raise Exception("Failed to initiate update conversation")

        parsed_response = json.loads(raw_response)

        if "response" not in parsed_response:
            raise Exception("Missing 'response' field in assistant reply")

        # Save conversation to DB
        conversation = Conversation(
            thread_id=update_conversation.thread_id,
            user_id=user_id,
            role=role,
            conversation_type="update"
        )
        self.conversation_dao.add_conversation(conversation)

        return {
            "thread_id": update_conversation.thread_id,
            "response": parsed_response["response"]
        }

    def continue_update_assistant(self, auth_token: str, thread_id: str, message: str):
        """
        Continue the update assistant conversation.
        Args:
            auth_token (str): The user's authentication token.
            thread_id (str): The thread ID for the conversation.
            message (str): The user's message to continue the conversation.
        Returns:
            dict: Assistant's response.
        """
        # Validate session
        sessions = self.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            raise Exception("Invalid auth token")
        user_id = sessions[0]['user_id']

        # Retrieve conversation
        conversation = self.conversation_dao.get_conversation_by_thread_user_conversation_type(
            thread_id, user_id, "update"
        )
        if not conversation:
            raise Exception("Conversation not found")

        # Fetch student info
        student = self.student_dao.get_student_by_id(user_id)
        if not student:
            raise Exception("Student not found")

        # Continue conversation
        update_conv = UpdateAssistant(ASSISTANT_ID_UPDATE, student, None, conversation.role == "instructor")
        update_conv.thread_id = thread_id

        try:
            response = update_conv.cont_conv(message)
            return {
                "response": response
            }
        except Exception as e:
            return {"error": str(e)}
