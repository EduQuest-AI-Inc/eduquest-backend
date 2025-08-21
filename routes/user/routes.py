from flask import Blueprint, jsonify, request
from .user_service import UserService
from flask_jwt_extended import decode_token
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
    except Exception:
        return jsonify({'message': 'Invalid or expired token'}), 401


