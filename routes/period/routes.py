from flask import Blueprint, request, jsonify
from .period_service import PeriodService

period_bp = Blueprint('period', __name__)
period_service = PeriodService()

@period_bp.route('/verify-period', methods=['POST'])
def verify_period():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        # Verify period and add to enrollments
        period = period_service.verify_period_id(auth_token, period_id)
        return jsonify({"message": "Period verified and added to enrollments", "period": period}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except LookupError as le:
        return jsonify({"error": str(le)}), 404
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@period_bp.route('/initiate-ltg-conversation', methods=['POST'])
def initiate_ltg_conversation():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        auth_token = auth_header.split(" ", 1)[1]

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        # You may want to pass auth_token and period_id to the service
        result = period_service.initiate_ltg_conversation(auth_token, period_id)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except LookupError as le:
        return jsonify({"error": str(le)}), 404

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@period_bp.route('/continue-ltg-conversation', methods=['POST'])
def continue_ltg_conversation():
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

        result = period_service.continue_ltg_conversation(auth_token, conversation_type, thread_id, user_message)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@period_bp.route('/initiate-schedules-agent', methods=['POST'])
def initiate_schedules_agent():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
        
        auth_token = auth_header.split(" ", 1)[1]
        data = request.json
        
        period_id = data.get('period_id')  
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        
        result = period_service.start_schedules_agent(auth_token, period_id)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in initiate-schedules-agent: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@period_bp.route('/initiate-homework-agent', methods=['POST'])
def initiate_homework_agent():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401
            
        auth_token = auth_header.split(" ", 1)[1]
        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        
        result = period_service.start_homework_agent(auth_token, period_id)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in initiate-homework-agent: {str(e)}")
        return jsonify({"error": str(e)}), 500