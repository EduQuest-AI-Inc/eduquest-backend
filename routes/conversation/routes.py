# routes/conversation.py
from flask import Blueprint, request, jsonify
from flask_cors import CORS
import json
# from data_access.conversation_dao import add_conversation, append_conversation, get_all_conversations

from assistants import ini_conv, summarize_conversation
from models.student_profile import student_profile
from openai import OpenAI
# import time
import os
from dotenv import load_dotenv
# from data_access
from routes.conversation.conversation_service import ConversationService

load_dotenv()

OpenAI.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sec_math_2 = {'initiate': 'asst_bmsuvfNCaHJYmqTlnT52AzXE',
    'update': 'asst_oQlKvMpoDPp80zEabjvUiflj'}

conversation_bp = Blueprint('conversation', __name__)
conversation_service = ConversationService()

# Routes
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
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        auth_token = auth_header.split(" ", 1)[1]

        conversation_type = data.get('conversation_type')
        thread_id = data.get('thread_id')
        user_message = data.get('message')

        if not conversation_type:
            return jsonify({"error": "conversation_type is required"}), 400

        if not thread_id:
            return jsonify({"error": "thread_id is required"}), 400

        if not user_message:
            return jsonify({"error": "user_message is required"}), 400
        
        result = conversation_service.continue_profile_assistant(auth_token, conversation_type, thread_id, user_message)
        return result, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500