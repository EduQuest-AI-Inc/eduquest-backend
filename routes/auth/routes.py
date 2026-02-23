# auth/routes.py

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import create_access_token, decode_token
from .auth_service import register_user, authenticate_user
from .password_reset_service import get_password_reset_service
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
password_reset_service = get_password_reset_service()
#sdf1234567890123456
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

    # Canonical lowercase email for consistent lookups
    email_lc = email.strip().lower()

    # Check uniqueness using email_lc to prevent case-based duplicates
    student_items = student_dao.table.scan(FilterExpression="email_lc = :email_lc", ExpressionAttributeValues={":email_lc": email_lc}).get("Items", [])
    teacher_items = teacher_dao.table.scan(FilterExpression="email_lc = :email_lc", ExpressionAttributeValues={":email_lc": email_lc}).get("Items", [])
    if student_items or teacher_items:
        return jsonify({'message': 'Email address already in use'}), 409

    result = register_user(username, password, role, first_name, last_name, email, email_lc, grade if role == 'student' else None)

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


def _get_client_ip():
    """Get the client's IP address, handling proxies."""
    # Check X-Forwarded-For header (set by load balancers/proxies)
    if request.headers.get('X-Forwarded-For'):
        # Take the first IP in the chain (original client)
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    # Check X-Real-IP header (alternative proxy header)
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP').strip()
    # Fall back to remote_addr
    return request.remote_addr or '0.0.0.0'


@auth_bp.route('/password-reset/request', methods=['POST'])
def password_reset_request():
    """
    Request a password reset email.
    Always returns a neutral success message to prevent email enumeration.
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400
    
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'message': 'Email is required'}), 400
    
    # Get client info
    ip_address = _get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    
    # Process the request
    result = password_reset_service.request_password_reset(
        email=email,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Always return 200 with neutral message
    return jsonify({'message': result['message']}), 200


@auth_bp.route('/password-reset/confirm', methods=['POST'])
def password_reset_confirm():
    """
    Confirm a password reset and set a new password.
    Uses a token from the reset email.
    """
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400
    
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '')
    
    if not token:
        return jsonify({'message': 'Reset token is required'}), 400
    
    if not new_password:
        return jsonify({'message': 'New password is required'}), 400
    
    # Get client IP
    ip_address = _get_client_ip()
    
    # Process the confirmation
    success, message = password_reset_service.confirm_password_reset(
        token=token,
        new_password=new_password,
        ip_address=ip_address
    )
    
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'message': message}), 400