# auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from .auth_service import register_user, authenticate_user
from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from models.session import Session
from routes.conversation.conversation_service import ConversationService

auth_bp = Blueprint('auth', __name__)
session_dao = SessionDAO()
student_dao = StudentDAO()
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
        access_token = create_access_token(identity=username)
        # Store session in DB
        session = Session(auth_token=access_token, user_id=username, role=role)
        session_dao.add_session(session)
        
        # If student, check if profile is blank
        if role == 'student':
            student = student_dao.get_student_by_id(username)[0]
            if not student.get('strength') or not student.get('weakness') or not student.get('interest') or not student.get('learning_style'):
                return jsonify({
                    'token': access_token,
                    'needs_profile': True
                }), 200
        
        return jsonify({'token': access_token}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401
