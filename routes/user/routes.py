from flask import Blueprint, jsonify, request
from .user_service import UserService
from flask_jwt_extended import jwt_required, get_jwt_identity

user_bp = Blueprint('user', __name__)
user_service = UserService()

@user_bp.route('/profile', methods=['GET'])
def get_profile():
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing or invalid"}), 401

    try:
        auth_token = auth_header.split(" ", 1)[1]
        user_data = user_service.get_user_profile(auth_token)
        return jsonify(user_data), 200

    except IndexError:
        return jsonify({"error": "Session data not found or malformed"}), 404

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@user_bp.route('/update-tutorial', methods=['POST'])
@jwt_required()
def update_tutorial():
    """Update tutorial completion status"""
    try:
        data = request.get_json()
        student_id = get_jwt_identity()
        
        completed_tutorial = data.get('completed_tutorial', False)
        
        user_service.update_tutorial_status(student_id, completed_tutorial)
        
        return jsonify({'message': 'Tutorial status updated successfully'}), 200
        
    except Exception as e:
        print(f"Error updating tutorial status: {e}")
        return jsonify({'error': 'Failed to update tutorial status'}), 500

@user_bp.route('/tutorial-status', methods=['GET'])
@jwt_required()
def get_tutorial_status():
    """Get current tutorial status"""
    try:
        student_id = get_jwt_identity()
        status = user_service.get_tutorial_status(student_id)
        
        return jsonify({'completed_tutorial': status}), 200
        
    except Exception as e:
        print(f"Error getting tutorial status: {e}")
        return jsonify({'error': 'Failed to get tutorial status'}), 500


