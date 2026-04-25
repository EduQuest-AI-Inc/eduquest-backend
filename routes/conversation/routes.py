import logging
from flask import Blueprint, request, jsonify
import json
import tempfile
import os
from routes.conversation.conversation_service import ConversationService
from utils.conversion_utils import convert_decimals
from utils.token_utils import extract_auth_token

logger = logging.getLogger(__name__)
conversation_bp = Blueprint('conversation', __name__)
conversation_service = ConversationService()


def _extract_auth_token():
    return extract_auth_token(request)


# ------------------------------------------------------------------
# Profile assistant
# ------------------------------------------------------------------

@conversation_bp.route('/initiate-profile-assistant', methods=['POST'])
def profile_assistant():
    try:
        auth_token = _extract_auth_token()
        result = conversation_service.start_profile_assistant(auth_token)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error in initiate-profile-assistant: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@conversation_bp.route('/continue-profile-assistant', methods=['POST'])
def continue_profile_assistant():
    try:
        data = request.json
        auth_token = _extract_auth_token()

        conversation_type = data.get('conversation_type')
        conversation_id = data.get('conversation_id')
        user_message = data.get('message')

        if not conversation_type:
            return jsonify({"error": "conversation_type is required"}), 400
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400
        if not user_message:
            return jsonify({"error": "message is required"}), 400

        result = conversation_service.continue_profile_assistant(
            auth_token, conversation_type, conversation_id, user_message,
        )
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error in continue-profile-assistant: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# Update assistant (grading / teacher feedback)
# ------------------------------------------------------------------

def _handle_file_submission(auth_token):
    """Handle multipart/form-data submissions (student file uploads)."""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file provided"}), 400

    individual_quest_id = request.form.get('individual_quest_id')
    week = request.form.get('week')
    if not individual_quest_id:
        return jsonify({"error": "individual_quest_id is required for student submissions"}), 400
    if not week:
        return jsonify({"error": "week is required for student submissions"}), 400

    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(file.filename)[1],
    )
    file.save(temp_file.name)
    temp_file.close()

    try:
        from data_access.quest_dao import QuestDAO
        quest_data = QuestDAO().get_quest_by_id(individual_quest_id)
        if not quest_data:
            return jsonify({"error": "Quest not found"}), 404
        quests_file = json.dumps([convert_decimals(quest_data)])
    except Exception as quest_error:
        return jsonify({"error": f"Failed to fetch quest: {quest_error}"}), 500

    result = conversation_service.start_update_assistant(
        auth_token=auth_token,
        quests_file=quests_file,
        is_instructor=False,
        week=int(week),
        submission_file=temp_file.name,
        user_id=request.form.get('user_id'),
        period_id=request.form.get('period_id'),
        individual_quest_id=individual_quest_id,
    )
    try:
        os.unlink(temp_file.name)
    except Exception:
        pass
    return jsonify(result), 200


def _handle_json_submission(auth_token):
    """Handle JSON body submissions (instructor or student without file upload)."""
    data = request.json
    quests_file = data.get('quests_file')
    is_instructor = data.get('is_instructor', False)
    week = data.get('week')
    submission_file = data.get('submission_file')

    if not quests_file:
        return jsonify({"error": "quests_file is required"}), 400
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
        user_id=data.get('user_id'),
        period_id=data.get('period_id'),
    )
    return jsonify(result), 200


@conversation_bp.route('/initiate-update-assistant', methods=['POST'])
def initiate_update():
    try:
        auth_token = _extract_auth_token()
        if request.files:
            return _handle_file_submission(auth_token)
        return _handle_json_submission(auth_token)
    except Exception as e:
        logger.error("Error in initiate-update-assistant: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@conversation_bp.route('/continue-update-assistant', methods=['POST'])
def continue_update():
    try:
        data = request.json
        auth_token = _extract_auth_token()

        conversation_id = data.get('conversation_id')
        user_message = data.get('message')
        user_id = data.get('user_id')

        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400
        if not user_message:
            return jsonify({"error": "message is required"}), 400

        result = conversation_service.continue_update_assistant(
            auth_token=auth_token,
            conversation_id=conversation_id,
            message=user_message,
            user_id=user_id,
        )
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error in continue-update-assistant: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500
