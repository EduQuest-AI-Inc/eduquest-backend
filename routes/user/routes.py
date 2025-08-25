from flask import Blueprint, jsonify, request
from .user_service import UserService
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO


user_bp = Blueprint('user', __name__)
user_service = UserService()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()

@user_bp.route('/profile', methods=['GET'])
def get_profile_cookie():
    token = request.cookies.get('auth_token')
    if not token:
        return jsonify({'message': 'Missing auth_token cookie'}), 401
    try:
        decoded = decode_token(token)
        username = decoded.get('sub')
        # Try student first
        student = student_dao.get_student_by_id(username)
        if student:
            return jsonify({'user': student}), 200
        # Try teacher
        teacher = teacher_dao.get_teacher_by_id(username)
        if teacher:
            return jsonify({'user': teacher}), 200
        return jsonify({'message': 'User not found'}), 404
    except Exception as e:
        print(f"Error in get_profile_cookie: {e}")
        return jsonify({'message': 'Invalid or expired token'}), 401

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


