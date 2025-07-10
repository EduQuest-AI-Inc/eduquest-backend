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
# ASSISTANT_ID_UPDATE = 'asst_oQlKvMpoDPp80zEabjvUiflj'   # update assistant

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

        Args:
            auth_token (str): The user's authentication token.
            quests_file (str): JSON string of quest data or path to the quests file.
            is_instructor (bool): Whether the user is an instructor.
            week (int, optional): Week number for student submissions.
            submission_file (str, optional): Path to the submission file for students.
            student_id (str, optional): Student ID when teacher is viewing student data.
            period_id (str, optional): Period ID when teacher is viewing student data.

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

        user_profile_dict = user  # user is already a dictionary, not a list
        print("DEBUG user_profile_dict:", user_profile_dict)

        # Get the update assistant ID from the period (same logic as LTG assistant)
        update_assistant_id = 'asst_oQlKvMpoDPp80zEabjvUiflj'  # Default assistant ID
        if period_id:
            period = self.period_dao.get_period_by_id(period_id)
            if period:
                custom_update_assistant_id = period.get('update_assistant_id')
                if custom_update_assistant_id and custom_update_assistant_id != "placeholder_update_assistant_id":
                    update_assistant_id = custom_update_assistant_id
                    print(f"Using custom update assistant ID: {update_assistant_id}")
                else:
                    print(f"Using default update assistant ID: {update_assistant_id}")
            else:
                print(f"Period {period_id} not found, using default assistant ID")
        else:
            print("No period_id provided, using default assistant ID")

        quests_data = None
        try:
            # parsing it as a json first
            quests_data = json.loads(quests_file)
            print("DEBUG: Using quest data from JSON string")
        except (json.JSONDecodeError, TypeError) as e:
            # treating it as a file path if that fails
            print(f"DEBUG: JSON parsing failed: {e}")
            print("DEBUG: Using quest data from file path")
            if is_instructor and student_id:
                try:
                    from routes.quest.quest_service import QuestService
                    quest_service = QuestService()
                    quests_data = quest_service.get_individual_quests_for_student(student_id)
                    print(f"DEBUG: Fetched {len(quests_data)} quests for student {student_id}")
                except Exception as quest_error:
                    print(f"DEBUG: Error fetching student quests: {quest_error}")
                    raise Exception(f"Failed to fetch student quests: {quest_error}")
            else:
                print("DEBUG: Using provided quests_file as is")
                try:
                    with open(quests_file, 'r') as f:
                        quests_data = json.load(f)
                except Exception as file_error:
                    print(f"DEBUG: Error loading quests from file: {file_error}")
                    raise Exception(f"Failed to load quests from file: {file_error}")

        update_conversation = UpdateAssistant(
            update_assistant_id,  # Use the custom or default assistant ID
            user_profile_dict,  
            quests_data,        
            is_instructor,
            week,
            submission_file
        )

        raw_response = update_conversation.initiate()
        print("Raw response from update_conversation.initiate():", raw_response)

        if not raw_response:
            raise Exception("Failed to initiate update conversation")

        if not is_instructor and week and student_id:
            try:
                response_data = json.loads(raw_response)
                grade = response_data.get('grade')
                feedback = response_data.get('feedback')
                
                if grade is not None and feedback is not None:
                    from routes.quest.quest_service import QuestService
                    quest_service = QuestService()
                    
                    individual_quests = quest_service.get_individual_quests_for_student(student_id)
                    target_quest = None
                    
                    # First try to find quest by week and period_id (if period_id is provided)
                    if period_id:
                        for quest in individual_quests:
                            if quest.get('week') == week and quest.get('period_id') == period_id:
                                target_quest = quest
                                break
                    
                    # If not found and period_id is None, try to find by week only
                    if not target_quest:
                        for quest in individual_quests:
                            if quest.get('week') == week:
                                target_quest = quest
                                print(f"Found quest by week only: {quest.get('individual_quest_id')} (period_id: {quest.get('period_id')})")
                                break
                    
                    if target_quest:
                        from data_access.individual_quest_dao import IndividualQuestDAO
                        quest_dao = IndividualQuestDAO()
                        quest_dao.update_quest_grade_and_feedback(
                            target_quest['individual_quest_id'],
                            str(grade),
                            feedback
                        )
                        print(f"Saved grade {grade} and feedback for quest {target_quest['individual_quest_id']}")
                    else:
                        print(f"Warning: Could not find individual quest for student {student_id}, week {week}, period {period_id}")
                        print(f"Available quests for student: {[(q.get('week'), q.get('period_id'), q.get('individual_quest_id')) for q in individual_quests]}")
                else:
                    print(f"Warning: Missing grade or feedback in response: {response_data}")
                    
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse assistant response as JSON: {e}")
                print(f"Raw response: {raw_response}")
            except Exception as e:
                print(f"Error saving grade and feedback: {e}")

        # update assistant returns a plain string       response_text = raw_response

        # saving conversation to DB
        conversation = Conversation(
            thread_id=update_conversation.thread_id,
            user_id=student_id if role == "teacher" and student_id else user_id,
            role=role,
            conversation_type="update",
            period_id=period_id
        )
        self.conversation_dao.add_conversation(conversation)

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

        update_assistant_id = 'asst_oQlKvMpoDPp80zEabjvUiflj'  # Default assistant ID
        period_id = conversation.get('period_id')
        if period_id:
            period = self.period_dao.get_period_by_id(period_id)
            if period:
                custom_update_assistant_id = period.get('update_assistant_id')
                if custom_update_assistant_id and custom_update_assistant_id != "placeholder_update_assistant_id":
                    update_assistant_id = custom_update_assistant_id
                    print(f"Using custom update assistant ID for continuation: {update_assistant_id}")
                else:
                    print(f"Using default update assistant ID for continuation: {update_assistant_id}")
            else:
                print(f"Period {period_id} not found, using default assistant ID for continuation")
        else:
            print("No period_id in conversation, using default assistant ID for continuation")

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
        update_conv = UpdateAssistant(update_assistant_id, student, quests_data, role == "teacher")
        update_conv.thread_id = thread_id

        try:
            response = update_conv.cont_conv(message)
            return {
                "response": response
            }
        except Exception as e:
            return {"error": str(e)}