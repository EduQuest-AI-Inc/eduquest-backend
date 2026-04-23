import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from routes.quest.quest_service import QuestService
from routes.quest.quest_retrieval_service import QuestRetrievalService
from data_access.supabase.quest_dao import QuestDAO
from data_access.supabase.enrollment_dao import EnrollmentDAO
from data_access.supabase.period_dao import PeriodDAO

logger = logging.getLogger(__name__)

quest_bp = Blueprint('quest', __name__)
quest_service = QuestService()
quest_dao = QuestDAO()
enrollment_dao = EnrollmentDAO()
period_dao = PeriodDAO()


@quest_bp.route('/quests', methods=['GET'])
@jwt_required()
def get_quests():
    try:
        user_id = get_jwt_identity()
        period_id = request.args.get('period_id')
        if period_id:
            quests = quest_service.get_quests_for_student_and_period(user_id, period_id)
        else:
            quests = quest_service.get_quests_for_student(user_id)
        for quest in quests:
            QuestRetrievalService.attach_grade_display(quest)
        return jsonify(quests), 200
    except Exception as e:
        logger.error("Error getting quests: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get quests"}), 500


@quest_bp.route('/quests/<user_id>', methods=['GET'])
@jwt_required()
def get_student_quests(user_id):
    """Teacher/parent route: fetch quests for a specific student."""
    try:
        caller_id = get_jwt_identity()
        # Authorization: caller must own a period the student is enrolled in,
        # or be the student themselves.
        if caller_id != user_id:
            enrollments = enrollment_dao.get_enrollments_by_student(user_id)
            period_ids = [e['period_id'] for e in enrollments]
            caller_periods = period_dao.get_periods_by_owner_id(caller_id)
            caller_period_ids = {p['period_id'] for p in caller_periods}
            if not any(pid in caller_period_ids for pid in period_ids):
                return jsonify({"error": "Not authorized"}), 403

        quests = quest_service.get_quests_for_student(user_id)
        for quest in quests:
            QuestRetrievalService.attach_grade_display(quest)
        return jsonify(quests), 200
    except Exception as e:
        logger.error("Error getting student quests: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get student quests"}), 500


@quest_bp.route('/quests/<quest_id>/status', methods=['PUT'])
@jwt_required()
def update_quest_status(quest_id):
    try:
        get_jwt_identity()  # auth check
        data = request.json
        status = data.get('status')
        if not status:
            return jsonify({"error": "status is required"}), 400
        if status not in ("not_started", "in_progress", "completed"):
            return jsonify({"error": "status must be one of: not_started, in_progress, completed"}), 400
        result = quest_service.update_quest_status(quest_id, status)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error updating quest status: %s", e, exc_info=True)
        return jsonify({"error": "Failed to update quest status"}), 500


@quest_bp.route('/quests/<quest_id>', methods=['GET'])
@jwt_required()
def get_quest(quest_id):
    try:
        get_jwt_identity()  # auth check
        quest = quest_dao.get_quest_by_id(quest_id)
        if quest:
            QuestRetrievalService.attach_grade_display(quest)
            return jsonify(quest), 200
        return jsonify({"error": "Quest not found"}), 404
    except Exception as e:
        logger.error("Error getting quest: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get quest"}), 500


@quest_bp.route('/quests/<quest_id>/grade', methods=['PUT'])
@jwt_required()
def grade_quest(quest_id):
    try:
        get_jwt_identity()  # auth check (teacher)
        data = request.json
        grade = data.get('grade')
        feedback = data.get('feedback')
        if not grade:
            return jsonify({"error": "grade is required"}), 400
        if not feedback:
            return jsonify({"error": "feedback is required"}), 400
        if not isinstance(grade, dict):
            return jsonify({"error": "grade must be a dict with overall_score and detailed_grade"}), 400
        quest_dao.update_quest_grade_and_feedback(quest_id, grade, feedback)
        return jsonify({
            "message": "Grade and feedback submitted successfully",
            "quest_id": quest_id,
        }), 200
    except Exception as e:
        logger.error("Error grading quest: %s", e, exc_info=True)
        return jsonify({"error": "Failed to grade quest"}), 500


@quest_bp.route('/grade/parse', methods=['POST'])
def parse_grade_data():
    try:
        data = request.json
        grade = data.get('grade')
        if grade is None:
            return jsonify({"error": "grade field is required"}), 400
        grade_info = quest_service.parse_grade_data(grade)
        return jsonify({"parsed_grade": grade_info, "display_grade": grade_info['display_grade']}), 200
    except Exception as e:
        logger.error("Error parsing grade data: %s", e, exc_info=True)
        return jsonify({"error": "Failed to parse grade data"}), 500


@quest_bp.route('/verify-quest-structure/<period_id>', methods=['GET'])
@jwt_required()
def verify_quest_structure(period_id):
    try:
        user_id = get_jwt_identity()
        verification = quest_service.verify_quest_structure(user_id, period_id)
        return jsonify(verification), 200
    except Exception as e:
        logger.error("Error verifying quest structure: %s", e, exc_info=True)
        return jsonify({"error": "Failed to verify quest structure"}), 500
