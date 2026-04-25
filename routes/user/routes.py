import logging

from canvasapi import Canvas
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from .user_service import UserService
from utils.token_utils import extract_auth_token
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.parent_dao import ParentDAO
from data_access.user_dao import UserDAO
from data_access.session_dao import SessionDAO

logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__)
user_service = UserService()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
parent_dao = ParentDAO()
user_dao = UserDAO()
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


_ROLE_FETCHERS = {
    'student': lambda uid: student_dao.get_student_by_id(uid),
    'teacher': lambda uid: teacher_dao.get_teacher_by_id(uid),
    'parent':  lambda uid: parent_dao.get_parent_by_id(uid),
}


def _fetch_user_profile(user_id):
    """Dispatch to the correct role DAO based on user.role. Returns profile dict or None."""
    user = user_dao.get_by_id(user_id)
    if not user:
        return None
    role = user.get('role')
    fetcher = _ROLE_FETCHERS.get(role)
    if not fetcher:
        return None
    profile = fetcher(user_id)
    if not profile:
        return None
    profile['role'] = role
    if profile.get('role') == 'student':
        profile.pop('canvas_api_key', None)
    if profile.get('role') == 'teacher':
        profile.setdefault('pilot_approved', False)
    return profile


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
        user_id = get_jwt_identity()
        completed_tutorial = data.get('completed_tutorial', False)
        user_service.update_tutorial_status(user_id, completed_tutorial)
        return jsonify({'message': 'Tutorial status updated successfully'}), 200
    except Exception as e:
        logger.error("Error updating tutorial status: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to update tutorial status'}), 500


@user_bp.route('/tutorial-status', methods=['GET'])
@jwt_required()
def get_tutorial_status():
    """Get current tutorial status"""
    try:
        user_id = get_jwt_identity()
        status = user_service.get_tutorial_status(user_id)
        return jsonify({'completed_tutorial': status}), 200
    except Exception as e:
        logger.error("Error getting tutorial status: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to get tutorial status'}), 500


@user_bp.route('/canvas/connect', methods=['POST'])
@jwt_required()
def canvas_connect():
    user_id = get_jwt_identity()
    data = request.get_json()
    api_url = data.get('api_url')
    api_key = data.get('api_key')
    if not api_url or not api_key:
        return jsonify({'error': 'api_url and api_key are required'}), 400
    try:
        canvas = Canvas(api_url, api_key)
        canvas.get_current_user()
    except Exception:
        return jsonify({'error': 'Invalid Canvas credentials. Check your URL and token.'}), 400
    student_dao.update_canvas_credentials(user_id, api_url, api_key)
    return jsonify({'message': 'Canvas connected'}), 200


@user_bp.route('/canvas/courses', methods=['GET'])
@jwt_required()
def canvas_courses():
    user_id = get_jwt_identity()
    student = student_dao.get_student_by_id(user_id)
    api_url = student.get('canvas_api_url')
    api_key = student.get('canvas_api_key')
    if not api_url or not api_key:
        return jsonify({'error': 'Canvas not connected'}), 400
    try:
        canvas = Canvas(api_url, api_key)
        current_user = canvas.get_current_user()
        courses = [
            {'id': c.id, 'name': getattr(c, 'name', f'Course {c.id}')}
            for c in current_user.get_courses(enrollment_type='student')
        ]
        return jsonify({'courses': courses}), 200
    except Exception as e:
        logger.error("Error fetching Canvas courses: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to fetch Canvas courses'}), 400


@user_bp.route('/canvas/disconnect', methods=['DELETE'])
@jwt_required()
def canvas_disconnect():
    user_id = get_jwt_identity()
    student_dao.clear_canvas_credentials(user_id)
    return jsonify({'message': 'Canvas disconnected'}), 200
