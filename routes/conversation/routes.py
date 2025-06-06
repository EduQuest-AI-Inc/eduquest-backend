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
from routes.conversation.conversation_service import start_conversation_service

load_dotenv()

OpenAI.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sec_math_2 = {'initiate': 'asst_bmsuvfNCaHJYmqTlnT52AzXE',
    'update': 'asst_oQlKvMpoDPp80zEabjvUiflj'}

conversation_bp = Blueprint('conversation', __name__)

# Routes
@conversation_bp.route('/start-conversation', methods=['POST'])
def start_conversation():
    # try:
    #     data = request.json
    #     auth_header = request.headers.get('Authorization')

    #     if not auth_header or not auth_header.startswith("Bearer "):
    #         return jsonify({"error": "Authorization header missing or invalid"}), 401

    #     auth_token = auth_header.split(" ", 1)[1]
    #     period_id = data.get('period_id')
    #     if not period_id:
    #         return jsonify({"error": "period_id is required"}), 400

    #     result = start_conversation_service(auth_token, period_id)
    #     return result, 200
    # except Exception as e:
    #     return jsonify({"error": str(e)}), 500
    return "Hello"


# (Continue defining other routes: /continue-conversation, /get-summary ...)


# @conversation_bp.route('/continue-conversation', methods=['POST'])
# def continue_conversation():
#     data = request.json
#     user_message = data['message']
#     student_id = data['name']
#     thread_id = data['thread_id']

#     student = student_profile(student_id, 12, "Female", 6)  # Placeholder
#     conversation = ini_conv(student)
#     conversation.thread_id = thread_id
#     conversation.student = student

#     response = conversation.cont_conv(user_message)
#     parsed_response = json.loads(response)

#     append_conversation(student_id, thread_id, {"role": "user", "message": user_message})
#     append_conversation(student_id, thread_id, {"role": "assistant", "message": parsed_response["response"]})

#     return {
#         "message": parsed_response["response"],
#         "has_enough_information": parsed_response["has_enough_information"]
#     }

# @conversation_bp.route('/get-summary', methods=['POST'])
# def get_summary():
#     try:
#         data = request.json
#         student_id = data['name']
#         thread_id = data['thread_id']

#         conversation_log = get_all_conversations(student_id, thread_id)

#         response = summarize_conversation(conversation_log)
#         parsed_response = json.loads(response)

#         return {"summary": parsed_response}

#     except Exception as e:
#         return jsonify({"error": str(e)}), 400
