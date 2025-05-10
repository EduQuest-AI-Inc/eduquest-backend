# routes/conversation.py
from flask import Blueprint, request, jsonify
from flask_cors import CORS
import json
from data_access.conversation_dao import add_conversation, append_conversation, get_all_conversations
from assistants import ini_conv, summarize_conversation
from models.student_profile import student_profile

conversation_bp = Blueprint('conversation', __name__)
CORS(conversation_bp, resources={r"/*": {"origins": "http://eduquest-frontend.s3-website.us-east-2.amazonaws.com"}})

# Routes
@conversation_bp.route('/start-conversation', methods=['POST'])
def start_conversation():
    data = request.json
    student = student_profile(data['name'], data['age'], data['gender'], data['grade'])

    conversation = ini_conv(student)
    response = conversation.initiate()
    parsed_response = json.loads(response)

    add_conversation(student.name, conversation.thread_id, str(conversation.assistant.id), conversation.conversation_log)

    return jsonify({
        "message": parsed_response["response"],
        "thread_id": conversation.thread_id
    })

# (Continue defining other routes: /continue-conversation, /get-summary ...)


@conversation_bp.route('/continue-conversation', methods=['POST'])
def continue_conversation():
    data = request.json
    user_message = data['message']
    student_id = data['name']
    thread_id = data['thread_id']

    student = student_profile(student_id, 12, "Female", 6)  # Placeholder
    conversation = ini_conv(student)
    conversation.thread_id = thread_id
    conversation.student = student

    response = conversation.cont_conv(user_message)
    parsed_response = json.loads(response)

    append_conversation(student_id, thread_id, {"role": "user", "message": user_message})
    append_conversation(student_id, thread_id, {"role": "assistant", "message": parsed_response["response"]})
    
    return {
        "message": parsed_response["response"],
        "has_enough_information": parsed_response["has_enough_information"]
    }

@conversation_bp.route('/get-summary', methods=['POST'])
def get_summary():
    try:
        data = request.json
        student_id = data['name']
        thread_id = data['thread_id']

        conversation_log = get_all_conversations(student_id, thread_id)

        response = summarize_conversation(conversation_log)
        parsed_response = json.loads(response)

        return {"summary": parsed_response}

    except Exception as e:
        return jsonify({"error": str(e)}), 400
