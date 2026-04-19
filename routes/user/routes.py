import logging
import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from .user_service import UserService
from utils.token_utils import extract_auth_token

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.teacher_dao import TeacherDAO
    from data_access.supabase.session_dao import SessionDAO
else:
    from data_access.student_dao import StudentDAO
    from data_access.teacher_dao import TeacherDAO
    from data_access.session_dao import SessionDAO

logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__)
user_service = UserService()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
session_dao = SessionDAO()


def _resolve_identity(token):
    """Return user_id from JWT claims or session fallback. Returns None if unresolvable."""
    try:
        claims = decode_token(token)
        username = claims.get('sub')
        if username:
            return username
    except Exception as e:
        logger.debug("JWT decode failed, falling back to session lookup: %s", e)

    session_data = session_dao.get_sessions_by_auth_token(token)
    return session_data[0]['user_id'] if session_data else None


def _fetch_user_profile(user_id):
    """Look up student then teacher by user_id. Returns profile dict with 'role', or None."""
    student = student_dao.get_student_by_id(user_id)
    if student:
        student['role'] = 'student'
        return student
    teacher = teacher_dao.get_teacher_by_id(user_id)
    if teacher:
        teacher['role'] = 'teacher'
        teacher.setdefault('pilot_approved', False)
        return teacher
    return None


@user_bp.route('/profile', methods=['GET'])
def get_profile_cookie():
    token = extract_auth_token(request)
    if not token:
        return jsonify({'message': 'Missing token'}), 401
    try:
        user_id = _resolve_identity(token)
        if not user_id:
            return jsonify({'message': 'Invalid or expired token'}), 401

        profile = _fetch_user_profile(user_id)
        if not profile:
            return jsonify({'message': 'User not found'}), 404
        return jsonify(profile), 200
    except Exception as e:
        logger.error("Error in get_profile_cookie: %s", e, exc_info=True)
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
        logger.error("Error updating tutorial status: %s", e, exc_info=True)
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
        logger.error("Error getting tutorial status: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to get tutorial status'}), 500
