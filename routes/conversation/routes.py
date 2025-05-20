# routes/conversation.py
from flask import Blueprint, request, jsonify
from flask_cors import CORS
import json
from data_access.conversation_dao import ConversationDAO
from assistants import ini_conv, summarize_conversation
from models.student_profile import student_profile
from datetime import datetime, timezone
from models.conversation import Conversation


conversation_bp = Blueprint('conversation', __name__)
CORS(conversation_bp, resources={r"/*": {"origins": "http://eduquest-frontend.s3-website.us-east-2.amazonaws.com"}})
dao = ConversationDAO()
timestamp = datetime.now(timezone.utc).isoformat()


# Routes
@conversation_bp.route('/start-conversation', methods=['POST'])
def start_conversation():
    data = request.json
    student = student_profile(data['name'], data['age'], data['gender'], data['grade'])

    conversation = ini_conv(student)
    response = conversation.initiate()
    parsed_response = json.loads(response)

    convo_model = Conversation(
        thread_id=conversation.thread_id,
        last_updated_at=timestamp,
        name=student.name,
        message=parsed_response["response"],
        role="assistant"
    )
    dao.add_conversation(convo_model)

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

    user_entry = Conversation(
        thread_id=thread_id,
        last_updated_at=timestamp,
        name=student_id,
        message=user_message,
        role="user"
    )
    dao.add_conversation(user_entry)

    assistant_entry = Conversation(
        thread_id=thread_id,
        last_updated_at=timestamp,
        name=student_id,
        message=parsed_response["response"],
        role="assistant"
    )
    dao.add_conversation(assistant_entry)
    
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

        conversation_log = dao.get_conversations_by_thread(thread_id)

        response = summarize_conversation(conversation_log)
        parsed_response = json.loads(response)

        return {"summary": parsed_response}

    except Exception as e:
        return jsonify({"error": str(e)}), 400
