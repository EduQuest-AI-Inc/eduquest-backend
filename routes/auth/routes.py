from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import create_access_token, decode_token
from .auth_service import register_user, authenticate_user
from .password_reset_service import get_password_reset_service
from utils.token_utils import set_auth_cookie
from utils.validation_utils import get_client_ip
import os
from datetime import datetime, timezone
if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.session_dao import SessionDAO
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.teacher_dao import TeacherDAO
    from data_access.supabase.parent_dao import ParentDAO
    from data_access.supabase.parent_invite_dao import ParentInviteDAO
else:
    from data_access.session_dao import SessionDAO
    from data_access.student_dao import StudentDAO
    from data_access.teacher_dao import TeacherDAO
    from data_access.parent_dao import ParentDAO
    from data_access.parent_invite_dao import ParentInviteDAO
from models.session import Session
from routes.conversation.conversation_service import ConversationService

auth_bp = Blueprint('auth', __name__)
session_dao = SessionDAO()
student_dao = StudentDAO()
teacher_dao = TeacherDAO()
parent_dao = ParentDAO()
parent_invite_dao = ParentInviteDAO()
conversation_service = ConversationService()
password_reset_service = get_password_reset_service()


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

    valid_roles = {'student', 'teacher', 'parent'}
    if not username or not password or not role or not first_name or not last_name or not email or (role == 'student' and not grade):
        return jsonify({'message': 'Username, password, role, first_name, last_name, email' + (', and grade' if role == 'student' else '') + ' required'}), 400

    if role not in valid_roles:
        return jsonify({'message': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}), 400

    # Canonical lowercase email for consistent lookups
    email_lc = email.strip().lower()

    # Check uniqueness using email_lc to prevent case-based duplicates
    if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
        student_items = student_dao.get_student_by_email_lc(email_lc)
        teacher_items = teacher_dao.get_teacher_by_email_lc(email_lc)
        parent_items = parent_dao.get_parent_by_email_lc(email_lc)
    else:
        from boto3.dynamodb.conditions import Attr
        student_items = student_dao.table.scan(FilterExpression=Attr("email_lc").eq(email_lc)).get("Items", [])
        teacher_items = teacher_dao.table.scan(FilterExpression=Attr("email_lc").eq(email_lc)).get("Items", [])
        parent_items = parent_dao.table.scan(FilterExpression=Attr("email_lc").eq(email_lc)).get("Items", [])
    if student_items or teacher_items or parent_items:
        return jsonify({'message': 'Email address already in use'}), 409

    invite_code = data.get('invite_code', '').strip().upper()

    result = register_user(username, password, role, first_name, last_name, email, email_lc, grade if role == 'student' else None)

    if result.get('success'):
        response_body = {'message': 'User registered successfully'}

        if role == 'student' and invite_code:
            try:
                invite = parent_invite_dao.get_invite_by_code(invite_code)
                if not invite:
                    response_body['invite_warning'] = 'Invite code not found. You can link your parent account later from your profile.'
                elif invite.get('used'):
                    response_body['invite_warning'] = 'Invite code has already been used. You can link your parent account later from your profile.'
                else:
                    expires_at_str = invite.get('expires_at', '')
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expires_at:
                        response_body['invite_warning'] = 'Invite code has expired. You can link your parent account later from your profile.'
                    else:
                        parent_id = invite.get('parent_id')
                        parent = parent_dao.get_parent_by_id(parent_id)
                        if not parent:
                            response_body['invite_warning'] = 'Parent account not found. You can link your parent account later from your profile.'
                        else:
                            linked_ids = parent.get('linked_student_ids') or []
                            if username not in linked_ids:
                                linked_ids.append(username)
                                vpc_verified_at = datetime.now(timezone.utc).isoformat()
                                parent_dao.update_parent(parent_id, {
                                    'linked_student_ids': linked_ids,
                                    'vpc_verified_at': vpc_verified_at,  # COPPA 2025 homeschool VPC record
                                })
                                parent_invite_dao.mark_used(invite_code)
                            response_body['parent_linked'] = True
            except Exception as invite_err:
                print(f'Warning: failed to process invite code during signup: {invite_err}')
                response_body['invite_warning'] = 'Could not process invite code. You can link your parent account later from your profile.'

        return jsonify(response_body), 201
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
        access_token = create_access_token(identity=username, additional_claims={"role": role})
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
        set_auth_cookie(resp, access_token)
        return resp
    else:
        return jsonify({'message': 'Invalid credentials'}), 401


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
    ip_address = get_client_ip(request)
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
    ip_address = get_client_ip(request)
    
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