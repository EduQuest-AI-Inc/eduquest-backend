import logging

from flask import Blueprint, request, jsonify
from routes.quest.quest_service import QuestService
from routes.quest.quest_retrieval_service import QuestRetrievalService
from utils.token_utils import extract_auth_token, get_user_id_from_token
from data_access.supabase.session_dao import SessionDAO
from data_access.supabase.individual_quest_dao import IndividualQuestDAO

logger = logging.getLogger(__name__)

quest_bp = Blueprint('quest', __name__)
quest_service = QuestService()
session_dao = SessionDAO()


def _get_user_id():
    return get_user_id_from_token(extract_auth_token(request), session_dao)


@quest_bp.route('/weekly-quests/<period_id>', methods=['GET'])
def get_weekly_quests(period_id):
    try:
        user_id = _get_user_id()
        weekly_quest = quest_service.get_weekly_quests_for_student(user_id, period_id)
        if weekly_quest:
            return jsonify(weekly_quest.model_dump()), 200
        return jsonify({"message": "No weekly quests found for this period"}), 404
    except Exception as e:
        logger.error("Error getting weekly quests: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get weekly quests"}), 500


@quest_bp.route('/individual-quests', methods=['GET'])
def get_individual_quests():
    try:
        user_id = _get_user_id()
        period_id = request.args.get('period_id')
        if period_id:
            quests = quest_service.get_individual_quests_for_student_and_period(user_id, period_id)
        else:
            quests = quest_service.get_individual_quests_for_student(user_id)
        for quest in quests:
            QuestRetrievalService.attach_grade_display(quest)
        return jsonify(quests), 200
    except Exception as e:
        logger.error("Error getting individual quests: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get individual quests"}), 500


@quest_bp.route('/individual-quests/<user_id>', methods=['GET'])
def get_student_individual_quests(user_id):
    try:
        _get_user_id()  # auth check
        quests = quest_service.get_individual_quests_for_student(user_id)
        for quest in quests:
            QuestRetrievalService.attach_grade_display(quest)
        return jsonify(quests), 200
    except Exception as e:
        logger.error("Error getting student individual quests: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get student individual quests"}), 500


@quest_bp.route('/weekly-quests/<quest_id>/individual-quests/<individual_quest_id>/status', methods=['PUT'])
def update_individual_quest_status(quest_id, individual_quest_id):
    try:
        _get_user_id()  # auth check
        data = request.json
        status = data.get('status')
        if not status:
            return jsonify({"error": "status is required"}), 400
        if status not in ("not_started", "in_progress", "completed"):
            return jsonify({"error": "status must be one of: not_started, in_progress, completed"}), 400
        result = quest_service.update_individual_quest_status(quest_id, individual_quest_id, status)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error updating individual quest status: %s", e, exc_info=True)
        return jsonify({"error": "Failed to update quest status"}), 500


@quest_bp.route('/weekly-quests/<quest_id>/individual-quests/<individual_quest_id>', methods=['GET'])
def get_individual_quest(quest_id, individual_quest_id):
    try:
        _get_user_id()  # auth check
        quest = quest_service.get_individual_quest_by_id(quest_id, individual_quest_id)
        if quest:
            return jsonify(quest.model_dump()), 200
        return jsonify({"error": "Individual quest not found"}), 404
    except Exception as e:
        logger.error("Error getting individual quest: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get individual quest"}), 500


@quest_bp.route('/verify-quest-structure/<period_id>', methods=['GET'])
def verify_quest_structure(period_id):
    try:
        user_id = _get_user_id()
        verification = quest_service.verify_quest_structure(user_id, period_id)
        return jsonify(verification), 200
    except Exception as e:
        logger.error("Error verifying quest structure: %s", e, exc_info=True)
        return jsonify({"error": "Failed to verify quest structure"}), 500


@quest_bp.route('/individual-quests/<individual_quest_id>/details', methods=['GET'])
def get_individual_quest_details(individual_quest_id):
    try:
        _get_user_id()  # auth check
        quest_dao = IndividualQuestDAO()
        quest = quest_dao.get_individual_quest_by_id(individual_quest_id)
        if quest:
            QuestRetrievalService.attach_grade_display(quest)
            return jsonify(quest), 200
        return jsonify({"error": "Individual quest not found"}), 404
    except Exception as e:
        logger.error("Error getting individual quest details: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get individual quest details"}), 500


@quest_bp.route('/grade/parse', methods=['POST'])
def parse_grade_data():
    try:
        data = request.json
        grade_str = data.get('grade')
        if grade_str is None:
            return jsonify({"error": "grade field is required"}), 400
        grade_info = quest_service.parse_grade_data(grade_str)
        return jsonify({"parsed_grade": grade_info, "display_grade": grade_info['display_grade']}), 200
    except Exception as e:
        logger.error("Error parsing grade data: %s", e, exc_info=True)
        return jsonify({"error": "Failed to parse grade data"}), 500


@quest_bp.route('/individual-quests/<individual_quest_id>/grade', methods=['PUT'])
def grade_individual_quest(individual_quest_id):
    try:
        _get_user_id()  # auth check (teacher)
        data = request.json
        grade = data.get('grade')
        feedback = data.get('feedback')
        if not grade:
            return jsonify({"error": "grade is required"}), 400
        if not feedback:
            return jsonify({"error": "feedback is required"}), 400
        quest_dao = IndividualQuestDAO()
        quest_dao.update_quest_grade_and_feedback(individual_quest_id, grade, feedback)
        return jsonify({
            "message": "Grade and feedback submitted successfully",
            "individual_quest_id": individual_quest_id,
            "grade": grade,
            "feedback": feedback,
        }), 200
    except Exception as e:
        logger.error("Error grading individual quest: %s", e, exc_info=True)
        return jsonify({"error": "Failed to grade quest"}), 500
