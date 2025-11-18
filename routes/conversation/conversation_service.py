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
from s3 import upload_file_to_s3

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
                               submission_file: str = None, student_id: str = None, period_id: str = None, individual_quest_id: str = None):
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
            individual_quest_id (str, optional): Individual quest ID for direct quest lookup.

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

        # Fetch user info
        user = self.teacher_dao.get_teacher_by_id(user_id) if role == "teacher" else self.student_dao.get_student_by_id(user_id)
        if not user:
            raise Exception(f"{role.capitalize()} not found")

        user_profile_dict = user
        print("DEBUG user_profile_dict:", user_profile_dict)

        if is_instructor:
            if not period_id:
                raise Exception("period_id is required for instructors")
        else:
            if not quests_file:
                raise Exception("quests_file is required for students")
            
            try:
                quests_data = json.loads(quests_file)
                if not quests_data or not isinstance(quests_data, list) or len(quests_data) == 0:
                    raise Exception("Invalid quests data format")
                
                period_id = quests_data[0].get('period_id')
                if not period_id:
                    raise Exception("No period_id found in quest data")
                
                print(f"Extracted period_id from quest data: {period_id}")
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse quests JSON: {e}")
        
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
            # For students, quests_data was already parsed when extracting period_id
            quests_data = json.loads(quests_file)
            print(f"Loaded {len(quests_data)} quests from JSON string")

        s3_key = None
        if not is_instructor and submission_file and period_id and student_id and individual_quest_id:
            import time
            timestamp = int(time.time())
            filename = f"{timestamp}_{os.path.basename(submission_file)}"
            folder = f"periods/{period_id}/students/{student_id}/{individual_quest_id}"
            s3_key = upload_file_to_s3(submission_file, filename=filename, folder=folder)
            print(f"Uploaded submission to S3: {s3_key}")
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

        if is_instructor:
            try:
                response_json = json.loads(raw_response)
                raw_response = response_json.get('response') or f"""\
Response: {response_json.get('feedback', 'No feedback')}
Grade: {response_json.get('grade', 'N/A')}
Recommended Changes: {response_json.get('recommended_change', 'None')}"""
            except json.JSONDecodeError:
                pass  # leave raw_response as-is

        # For student grading, save grade and feedback FIRST before any agent processing
        if not is_instructor and week and student_id:
            try:
                response_data = json.loads(raw_response)

                grade = response_data.get('grade')
                overall_score = response_data.get('overall_score')
                feedback = response_data.get('feedback')
                change = response_data.get('change')
                recommended_change = response_data.get('recommended_change')

                # PRIORITY 1: Save grade and feedback immediately (before any agent calls)
                # This ensures grades are preserved even if quest updates fail
                # if grade is not None and feedback is not None:

                print(f"DEBUG: Saving grade and feedback before any agent processing...")
                
                # Use direct quest lookup if individual_quest_id is provided (much more efficient)
                if individual_quest_id:
                    from data_access.individual_quest_dao import IndividualQuestDAO
                    quest_dao = IndividualQuestDAO()
                    
                    # Store both the detailed grade object and the overall score
                    grade_data = {
                        "detailed_grade": grade,
                        "overall_score": overall_score
                    }
                    
                    quest_dao.update_quest_grade_and_feedback(
                        individual_quest_id,
                        json.dumps(grade_data),  # Store as JSON string
                        feedback
                    )
                    print(f"✅ SAVED rubric-based grade {overall_score} and feedback for quest {individual_quest_id}")
                else:
                    # Fallback to old method if individual_quest_id is not provided
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
                        
                        # Store both the detailed grade object and the overall score
                        grade_data = {
                            "detailed_grade": grade,
                            "overall_score": overall_score
                        }
                        
                        quest_dao.update_quest_grade_and_feedback(
                            target_quest['individual_quest_id'],
                            json.dumps(grade_data),  # Store as JSON string
                            feedback
                        )
                        print(f"✅ SAVED rubric-based grade {overall_score} and feedback for quest {target_quest['individual_quest_id']}")
                    else:
                        print(f"❌ WARNING: Could not find individual quest for student {student_id}, week {week}, period {period_id}")
                        print(f"Available quests for student: {[(q.get('week'), q.get('period_id'), q.get('individual_quest_id')) for q in individual_quests]}")
                    
                    # except Exception as save_error:
                    #     print(f"❌ ERROR saving grade and feedback: {save_error}")
                    #     # Don't re-raise - we want to continue with quest updates even if grade save fails
                    #     import traceback
                    #     traceback.print_exc()
                # else:
                #     print(f"DEBUG: Skipping grade save - grade: {grade}, feedback: {feedback}")
                
                # PRIORITY 2: Handle quest updates (separate from grade saving)
                # This happens AFTER grades are safely saved
                if change and recommended_change and period_id:
                    try:
                        print(f"DEBUG: Change recommended - updating future quests")
                        print(f"DEBUG: Recommended change: {recommended_change}")
                        
                        # Import PeriodService to trigger quest updates
                        from routes.period.period_service import PeriodService
                        period_service = PeriodService()
                        
                        # Update quests with the recommended changes
                        quest_update_result = period_service.update_quests_with_recommended_change(
                            auth_token, 
                            period_id, 
                            recommended_change
                        )
                        
                        print(f"DEBUG: Quest update completed: {quest_update_result.get('message', 'No message')}")
                        print(f"DEBUG: Updated {quest_update_result.get('updated_quests', 0)} quests")
                        
                        # Update the response to include quest update information
                        try:
                            # Parse the original response and add quest update info
                            response_dict = json.loads(raw_response)
                            response_dict['quest_update_performed'] = True
                            response_dict['quest_update_result'] = quest_update_result
                            raw_response = json.dumps(response_dict)
                            print("DEBUG: Updated response with quest update information")
                        except json.JSONDecodeError:
                            # If raw_response is not JSON, append the information as text
                            raw_response += f"\n\nAdditionally, your future quests have been updated based on this feedback: {recommended_change}"
                            print("DEBUG: Appended quest update information to text response")
                            
                    except Exception as quest_update_error:
                        print(f"ERROR: Failed to update quests with recommended change: {quest_update_error}")
                        # Don't fail the entire request if quest update fails
                        # Just log the error and continue
                        import traceback
                        traceback.print_exc()
                
                elif change and not recommended_change:
                    print("WARNING: Change was recommended but no recommended_change text provided")
                elif change and not period_id:
                    print("WARNING: Change was recommended but no period_id provided for quest updates")
                else:
                    print("DEBUG: No change recommended or change is False - no quest updates needed")
                    
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse assistant response as JSON: {e}")
                print(f"Raw response: {raw_response}")
            except Exception as e:
                print(f"Error saving grade and feedback: {e}")

        # For teacher conversations, check if change is recommended in the initial response
        if is_instructor and period_id:
            try:
                # Try to parse the response as JSON to check for change recommendations
                response_data = json.loads(raw_response)
                change = response_data.get('change', False)
                recommended_change = response_data.get('recommended_change', '')
                
                print(f"DEBUG: Teacher initial conversation - change: {change}, recommended_change: {recommended_change}")
                
                # If change is recommended, update future quests
                if change and recommended_change:
                    print(f"DEBUG: Teacher recommended changes in initial response - updating future quests")
                    print(f"DEBUG: Recommended change: {recommended_change}")
                    
                    # Import PeriodService to trigger quest updates
                    from routes.period.period_service import PeriodService
                    period_service = PeriodService()
                    
                    # Update quests with the recommended changes
                    quest_update_result = period_service.update_quests_with_recommended_change(
                        auth_token, 
                        period_id, 
                        recommended_change,
                        student_id  # Pass the student_id for teacher conversations
                    )
                    
                    print(f"DEBUG: Quest update completed: {quest_update_result.get('message', 'No message')}")
                    print(f"DEBUG: Updated {quest_update_result.get('updated_quests', 0)} quests")
                    
                    # Update the response to include quest update information
                    try:
                        response_dict = json.loads(raw_response)
                        response_dict['quest_update_performed'] = True
                        response_dict['quest_update_result'] = quest_update_result
                        response_dict['response'] += f"\n\nI've updated the student's future quests based on your recommendations. {quest_update_result.get('message', '')}"
                        raw_response = json.dumps(response_dict)
                        print("DEBUG: Updated initial response with quest update information")
                    except json.JSONDecodeError:
                        # If raw_response is not JSON, append the information as text
                        raw_response += f"\n\nI've updated the student's future quests based on your recommendations. {quest_update_result.get('message', '')}"
                        print("DEBUG: Appended quest update information to initial text response")
                        
                elif change and not recommended_change:
                    print("WARNING: Change was recommended but no recommended_change text provided in initial response")
                else:
                    print("DEBUG: No change recommended in initial response or change is False")
                    
            except json.JSONDecodeError:
                print("DEBUG: Initial response is not JSON, skipping change detection for teacher")
            except Exception as quest_update_error:
                print(f"ERROR: Failed to update quests with recommended change in initial response: {quest_update_error}")
                # Don't fail the entire request if quest update fails
                import traceback
                traceback.print_exc()

        # update assistant returns a plain string       response_text = raw_response

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
            "response": raw_response,
            **({"s3_key": s3_key} if s3_key else {})
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
            

            # If this is a teacher conversation, check for change recommendations
            if role == "teacher" and period_id:
                try:
                    # Try to parse the response as JSON to check for change recommendations
                    response_data = json.loads(response)
                    change = response_data.get('change', False)
                    recommended_change = response_data.get('recommended_change', '')
                    
                    print(f"DEBUG: Teacher conversation - change: {change}, recommended_change: {recommended_change}")
                    
                    # If change is recommended, update future quests
                    if change and recommended_change:
                        print(f"DEBUG: Teacher recommended changes - updating future quests")
                        print(f"DEBUG: Recommended change: {recommended_change}")
                        
                        # Import PeriodService to trigger quest updates
                        from routes.period.period_service import PeriodService
                        period_service = PeriodService()
                        
                        # Update quests with the recommended changes
                        quest_update_result = period_service.update_quests_with_recommended_change(
                            auth_token, 
                            period_id, 
                            recommended_change,
                            target_user_id  # Pass the target_user_id (which is student_id for teacher conversations)
                        )
                        
                        print(f"DEBUG: Quest update completed: {quest_update_result.get('message', 'No message')}")
                        print(f"DEBUG: Updated {quest_update_result.get('updated_quests', 0)} quests")
                        
                        # Update the response to include quest update information
                        try:
                            response_dict = json.loads(response)
                            response_dict['quest_update_performed'] = True
                            response_dict['quest_update_result'] = quest_update_result
                            response_dict['response'] += f"\n\nI've updated the student's future quests based on your recommendations. {quest_update_result.get('message', '')}"
                            response = json.dumps(response_dict)
                            print("DEBUG: Updated response with quest update information")
                        except json.JSONDecodeError:
                            # If response is not JSON, append the information as text
                            response += f"\n\nI've updated the student's future quests based on your recommendations. {quest_update_result.get('message', '')}"
                            print("DEBUG: Appended quest update information to text response")
                            
                    elif change and not recommended_change:
                        print("WARNING: Change was recommended but no recommended_change text provided")
                    else:
                        print("DEBUG: No change recommended or change is False - no quest updates needed")
                        
                    # For teacher conversations, extract just the response text for display
                    try:
                        response_data = json.loads(response)
                        if 'response' in response_data:
                            response = response_data['response']
                        else:
                            # If no response field, return formatted JSON for debugging
                            response = json.dumps(response_data, indent=2)
                    except json.JSONDecodeError:
                        # Response is already plain text, use as is
                        pass
                        
                except json.JSONDecodeError:
                    print("DEBUG: Response is not JSON, skipping change detection for teacher")
                except Exception as quest_update_error:
                    print(f"ERROR: Failed to update quests with recommended change: {quest_update_error}")
                    # Don't fail the entire request if quest update fails
                    import traceback
                    traceback.print_exc()
            
            return {
                "response": response
            }
        except Exception as e:
            print(f"Error in continue_update_assistant: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}