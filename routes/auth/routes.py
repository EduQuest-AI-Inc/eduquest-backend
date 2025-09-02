# auth/routes.py

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import create_access_token, decode_token
from .auth_service import register_user, authenticate_user, verify_email_code, resend_verification_code
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from models.session import Session
from routes.conversation.conversation_service import ConversationService

auth_bp = Blueprint('auth', __name__)
session_dao = SessionDAO()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
conversation_service = ConversationService()

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400

    username = data.get('username')
    password = data.get('password')
    role = data.get('role')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    grade = data.get('grade')

    if not username or not password or not role or not first_name or not last_name or not email or (role == 'student' and not grade):
        return jsonify({'message': 'Username, password, role, first_name, last_name, email' + (', and grade' if role == 'student' else '') + ' required'}), 400

    # Check if email already exists for student or teacher
    student_items = student_dao.table.scan(FilterExpression="email = :email", ExpressionAttributeValues={":email": email}).get("Items", [])
    teacher_items = teacher_dao.table.scan(FilterExpression="email = :email", ExpressionAttributeValues={":email": email}).get("Items", [])
    if student_items or teacher_items:
        return jsonify({'message': 'Email address already in use'}), 409

    if register_user(username, password, role, first_name, last_name, email, grade if role == 'student' else None):
        return jsonify({'message': 'User registered successfully'}), 201
    else:
        return jsonify({'message': 'Username already exists'}), 409

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400

    username = data.get('username')
    password = data.get('password')
    role = data.get('role')

    if not username or not password or not role:
        return jsonify({'message': 'Username, password, and role required'}), 400

    if authenticate_user(username, password, role):
        # Block login for unverified users
        user = student_dao.get_student_by_id(username) if role == 'student' else teacher_dao.get_teacher_by_id(username)
        if user and not user.get('email_verified', False):
            return jsonify({'message': 'Email not verified', 'needs_verification': True}), 403
        access_token = create_access_token(identity=username)
        session = Session(auth_token=access_token, user_id=username, role=role)
        session_dao.add_session(session)
        response_data = {'token': access_token}
        # If student, check if profile is blank
        if role == 'student':
            student = student_dao.get_student_by_id(username)
            if not student.get('strength') or not student.get('weakness') or not student.get('interest') or not student.get('learning_style'):
                response_data['needs_profile'] = True
        # Set cookie
        resp = make_response(jsonify(response_data), 200)
        resp.set_cookie(
            'auth_token',
            access_token,
            httponly=False, 
            secure=True,           # Required for HTTPS
            samesite='None',       # Allows cross-site cookies
            domain='eduquestai.org',
            path="/"  
        )
        return resp
    else:
        return jsonify({'message': 'Invalid credentials'}), 401


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400
    username = data.get('username')
    role = data.get('role')
    code = data.get('code')
    if not username or not role or not code:
        return jsonify({'message': 'username, role, and code required'}), 400
    ok = verify_email_code(username, role, code)
    if ok:
        return jsonify({'message': 'Email verified successfully'}), 200
    return jsonify({'message': 'Invalid or expired code'}), 400


@auth_bp.route('/resend-code', methods=['POST'])
def resend_code():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400
    username = data.get('username')
    role = data.get('role')
    if not username or not role:
        return jsonify({'message': 'username and role required'}), 400
    ok = resend_verification_code(username, role)
    if ok:
        return jsonify({'message': 'Verification code resent'}), 200
    return jsonify({'message': 'User not found'}), 404