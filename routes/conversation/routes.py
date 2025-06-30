# routes/conversation.py
from flask import Blueprint, request, jsonify
from flask_cors import CORS
import json
import time
import tempfile
from decimal import Decimal
from assistants import ini_conv, summarize_conversation
# from EQ_agents.agent import SchedulesAgent
from models.student_profile import student_profile
from openai import OpenAI
import os
from dotenv import load_dotenv
from routes.conversation.conversation_service import ConversationService

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

assistant_ids = {
    "initial": "asst_bmsuvfNCaHJYmqTlnT52AzXE",
    "update": "asst_oQlKvMpoDPp80zEabjvUiflj"
}

conversation_bp = Blueprint('conversation', __name__)
conversation_service = ConversationService()


def convert_decimals(obj):
    """Convert Decimal objects to regular numbers for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    else:
        return obj


# Routes for profile assistant
@conversation_bp.route('/initiate-profile-assistant', methods=['POST'])
def profile_assistant():
    try:
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        auth_token = auth_header.split(" ", 1)[1]

        result = conversation_service.start_profile_assistant(auth_token)
        return result, 200
    except Exception as e:
        print(f"Error in initiate-profile-assistant: {e}")
        return jsonify({"error": str(e)}), 500


@conversation_bp.route('/continue-profile-assistant', methods=['POST'])
def continue_profile_assistant():
    try:
        data = request.json
        print("Received data:", data)  # Debug log
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        auth_token = auth_header.split(" ", 1)[1]

        conversation_type = data.get('conversation_type')
        thread_id = data.get('thread_id')
        user_message = data.get('message')

        print(f"Parsed data - conversation_type: {conversation_type}, thread_id: {thread_id}, message: {user_message}")  # Debug log

        if not conversation_type:
            return jsonify({"error": "conversation_type is required"}), 400

        if not thread_id:
            return jsonify({"error": "thread_id is required"}), 400

        if not user_message:
            return jsonify({"error": "user_message is required"}), 400

        result = conversation_service.continue_profile_assistant(auth_token, conversation_type, thread_id, user_message)
        return result, 200
    except Exception as e:
        print(f"Error in continue-profile-assistant: {str(e)}")  
        import traceback
        print(f"Traceback: {traceback.format_exc()}")  
        return jsonify({"error": str(e)}), 500


@conversation_bp.route('/initiate-update-assistant', methods=['POST'])
def initiate_update():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        auth_token = auth_header.split(" ", 1)[1]
        
        # Check if this is a file upload (FormData) or JSON request
        if request.files:
            # Handle file upload from student
            print("Handling file upload request")
            
            # Get the uploaded file
            file = request.files.get('file')
            if not file:
                return jsonify({"error": "No file provided"}), 400
            
            # Save file to temporary location
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
            file.save(temp_file.name)
            temp_file.close()
            
            print(f"Saved uploaded file to: {temp_file.name}")
            
            # Get other form data
            week = request.form.get('week')
            student_id = request.form.get('student_id')
            period_id = request.form.get('period_id')
            
            if not week:
                return jsonify({"error": "week is required for student submissions"}), 400
            
            # For student submissions, we need to fetch their quests
            try:
                from routes.quest.quest_service import QuestService
                quest_service = QuestService()
                quests_data = quest_service.get_individual_quests_for_student(student_id)
                # Convert Decimal objects to regular numbers for JSON serialization
                quests_data = convert_decimals(quests_data)
                quests_file = json.dumps(quests_data)
                print(f"Fetched {len(quests_data)} quests for student {student_id}")
            except Exception as quest_error:
                print(f"Error fetching student quests: {quest_error}")
                return jsonify({"error": f"Failed to fetch student quests: {quest_error}"}), 500
            
            result = conversation_service.start_update_assistant(
                auth_token=auth_token,
                quests_file=quests_file,
                is_instructor=False,
                week=int(week),
                submission_file=temp_file.name,
                student_id=student_id,
                period_id=period_id
            )
            
            # Clean up temporary file after processing
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                print(f"Warning: Could not delete temporary file {temp_file.name}: {e}")
            
            return jsonify(result), 200
            
        else:
            # Handle JSON request (for teachers)
            print("Handling JSON request")
            data = request.json

            # Required fields
            quests_file = data.get('quests_file')
            is_instructor = data.get('is_instructor', False)

            print("DATA RECEIVED:", data)

            if not quests_file:
                return jsonify({"error": "quests_file is required"}), 400

            # Optional fields for student submissions
            week = data.get('week')
            submission_file = data.get('submission_file')
            student_id = data.get('student_id')
            period_id = data.get('period_id')

            # Validate student-specific fields
            if not is_instructor:
                if not week:
                    return jsonify({"error": "week is required for student submissions"}), 400
                if not submission_file:
                    return jsonify({"error": "submission_file is required for student submissions"}), 400

            result = conversation_service.start_update_assistant(
                auth_token=auth_token,
                quests_file=quests_file,
                is_instructor=is_instructor,
                week=week,
                submission_file=submission_file,
                student_id=student_id,
                period_id=period_id
            )
            return jsonify(result), 200
            
    except Exception as e:
        print(f"Error in initiate-update-assistant: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

    print("DEBUG user profile keys:", user_profile_dict.keys())
    print("DEBUG full user profile:", user_profile_dict)

@conversation_bp.route('/continue-update-assistant', methods=['POST'])
def continue_update():
    try:
        data = request.json
        print("[DEBUG] Received data:", data)
        auth_header = request.headers.get('Authorization')
        print("[DEBUG] Auth header:", auth_header)

        if not auth_header or not auth_header.startswith("Bearer "):
            print("[DEBUG] Missing or invalid auth header")
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        auth_token = auth_header.split(" ", 1)[1]
        print("[DEBUG] Auth token:", auth_token)

        thread_id = data.get('thread_id')
        user_message = data.get('message')
        student_id = data.get('student_id')

        print(f"[DEBUG] thread_id: {thread_id}, user_message: {user_message}, student_id: {student_id}")

        if not thread_id:
            print("[DEBUG] Missing thread_id")
            return jsonify({"error": "thread_id is required"}), 400

        if not user_message:
            print("[DEBUG] Missing message")
            return jsonify({"error": "message is required"}), 400

        result = conversation_service.continue_update_assistant(
            auth_token=auth_token,
            thread_id=thread_id,
            message=user_message,
            student_id=student_id
        )
        print("[DEBUG] Result from service:", result)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        print(f"[DEBUG] Exception in continue-update-assistant: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500