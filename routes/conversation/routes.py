# routes/conversation.py
from flask import Blueprint, request, jsonify
from flask_cors import CORS
import json
import time
from assistants import ini_conv, summarize_conversation
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


# Direct assistant route (no DB)
@conversation_bp.route("/conversation", methods=["POST"])
def handle_conversation():
    data = request.get_json()

    mode = data.get("mode")  # should be 'initial' or 'update'
    message = data.get("message")

    if not mode or mode not in assistant_ids:
        return jsonify({"error": "Invalid or missing mode (expected 'initial' or 'update')"}), 400
    if not message:
        return jsonify({"error": "Missing message"}), 400

    try:
        assistant_id = assistant_ids[mode]

        # Create new thread
        thread = client.beta.threads.create()

        # Send user message
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        # Poll until complete
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)

        # Get the reply
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        reply = messages.data[0].content[0].text.value

        return jsonify({
            "reply": reply,
            "thread_id": thread.id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
