# auth/routes.py

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import create_access_token, decode_token
from .auth_service import register_user, authenticate_user
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
#sdf12345678901
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
    waitlist_code = data.get('waitlistID')

    if not username or not password or not role or not first_name or not last_name or not email or not waitlist_code or (role == 'student' and not grade):
        return jsonify({'message': 'Username, password, role, first_name, last_name, email, waitlist code' + (', and grade' if role == 'student' else '') + ' required'}), 400

    student_items = student_dao.table.scan(FilterExpression="email = :email", ExpressionAttributeValues={":email": email}).get("Items", [])
    teacher_items = teacher_dao.table.scan(FilterExpression="email = :email", ExpressionAttributeValues={":email": email}).get("Items", [])
    if student_items or teacher_items:
        return jsonify({'message': 'Email address already in use'}), 409

    result = register_user(username, password, role, first_name, last_name, email, grade if role == 'student' else None, waitlist_code)

    if result.get('success'):
        return jsonify({'message': 'User registered successfully'}), 201
    else:
        error_message = result.get('error', 'Registration failed')
        status_code = 409 if 'already exists' in error_message else 400
        return jsonify({'message': error_message}), status_code

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
        
        # Determine if we're in development or production
        is_development = request.headers.get('Origin', '').startswith('http://localhost') or \
                        request.headers.get('Host', '').startswith('localhost') or \
                        request.headers.get('Host', '').startswith('127.0.0.1')
        
        if is_development:
            # Development settings
            resp.set_cookie(
                'auth_token',
                access_token,
                httponly=False,
                secure=False,         # No HTTPS in development
                samesite='Lax',       # More permissive for development
                path="/"
            )
        else:
            # Production settings
            resp.set_cookie(
                'auth_token',
                access_token,
                httponly=False,
                secure=True,          # HTTPS required in production
                samesite='None',      # Cross-site cookies for production
                domain='eduquestai.org',
                path="/"
            )
        return resp
    else:
        return jsonify({'message': 'Invalid credentials'}), 401