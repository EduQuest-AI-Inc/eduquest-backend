from flask import Blueprint, request, jsonify
from routes.quest.quest_service import QuestService
from data_access.session_dao import SessionDAO

quest_bp = Blueprint('quest', __name__)
quest_service = QuestService()
session_dao = SessionDAO()

@quest_bp.route('/weekly-quests/<period_id>', methods=['GET'])
def get_weekly_quests(period_id):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        sessions = session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401
        user_id = sessions[0]['user_id']

        weekly_quest = quest_service.get_weekly_quests_for_student(user_id, period_id)
        if weekly_quest:
            return jsonify(weekly_quest.model_dump()), 200
        else:
            return jsonify({"message": "No weekly quests found for this period"}), 404
    except Exception as e:
        print(f"Error getting weekly quests: {str(e)}")
        return jsonify({"error": "Failed to get weekly quests"}), 500

@quest_bp.route('/individual-quests', methods=['GET'])
def get_individual_quests():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        sessions = session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401
        user_id = sessions[0]['user_id']

        quests = quest_service.get_individual_quests_for_student(user_id)
        return jsonify(quests), 200
    except Exception as e:
        print(f"Error getting individual quests: {str(e)}")
        return jsonify({"error": "Failed to get individual quests"}), 500

@quest_bp.route('/individual-quests/<student_id>', methods=['GET'])
def get_student_individual_quests(student_id):
    """Get individual quests for a specific student (for teachers)."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        sessions = session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401
        teacher_id = sessions[0]['user_id']

        # we still need to add authorization check to ensure the teacher has access to this student. 
        # for now, any authenticated user can view any student's quests
        
        quests = quest_service.get_individual_quests_for_student(student_id)
        return jsonify(quests), 200
    except Exception as e:
        print(f"Error getting student individual quests: {str(e)}")
        return jsonify({"error": "Failed to get student individual quests"}), 500

@quest_bp.route('/weekly-quests/<weekly_quest_id>/individual-quests/<individual_quest_id>/status', methods=['PUT'])
def update_individual_quest_status(weekly_quest_id, individual_quest_id):
    """Update the status of a specific individual quest within a weekly quest list."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        sessions = session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401

        data = request.json
        status = data.get('status')
        if not status:
            return jsonify({"error": "status is required"}), 400

        if status not in ["not_started", "in_progress", "completed"]:
            return jsonify({"error": "status must be one of: not_started, in_progress, completed"}), 400

        result = quest_service.update_individual_quest_status(weekly_quest_id, individual_quest_id, status)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error updating individual quest status: {str(e)}")
        return jsonify({"error": "Failed to update quest status"}), 500

@quest_bp.route('/weekly-quests/<weekly_quest_id>/individual-quests/<individual_quest_id>', methods=['GET'])
def get_individual_quest(weekly_quest_id, individual_quest_id):
    """Get a specific individual quest from a weekly quest list."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        sessions = session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401

        quest = quest_service.get_individual_quest_by_id(weekly_quest_id, individual_quest_id)
        if quest:
            return jsonify(quest.model_dump()), 200
        else:
            return jsonify({"error": "Individual quest not found"}), 404
    except Exception as e:
        print(f"Error getting individual quest: {str(e)}")
        return jsonify({"error": "Failed to get individual quest"}), 500

@quest_bp.route('/verify-quest-structure/<period_id>', methods=['GET'])
def verify_quest_structure(period_id):
    """Verify that quests are saved correctly in both tables."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        sessions = session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401
        user_id = sessions[0]['user_id']

        verification = quest_service.verify_quest_structure(user_id, period_id)
        return jsonify(verification), 200
    except Exception as e:
        print(f"Error verifying quest structure: {str(e)}")
        return jsonify({"error": "Failed to verify quest structure"}), 500 