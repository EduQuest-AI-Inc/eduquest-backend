import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .period_service import PeriodService

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.parent_dao import ParentDAO
    from data_access.supabase.parent_invite_dao import ParentInviteDAO
else:
    from data_access.parent_dao import ParentDAO
    from data_access.parent_invite_dao import ParentInviteDAO

period_bp = Blueprint('period', __name__)
period_service = PeriodService()
_parent_dao = ParentDAO()
_invite_dao = ParentInviteDAO()

@period_bp.route('/my-periods', methods=['GET'])
def my_periods():
    try:
        auth_token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.lower().startswith('bearer '):
            auth_token = auth_header.split(' ', 1)[1].strip()

        if not auth_token:
            raw_cookie = request.headers.get('Cookie', '')
            if 'auth_token=' in raw_cookie:
                parts = [p.strip() for p in raw_cookie.split(';')]
                auth_tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
                if auth_tokens:
                    auth_token = auth_tokens[-1]

        if not auth_token:
            return jsonify({"error": "Missing auth token"}), 401

        result = period_service.get_my_periods(auth_token)
        return jsonify(result), 200

    except Exception as e:
        print(f"Unexpected error in my-periods: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@period_bp.route('/verify-period', methods=['POST'])
def verify_period():
    try:
        
        
        # Prefer Authorization: Bearer <token>
        auth_token = None
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            auth_token = token


        # Fallback: parse the last auth_token from Cookie header if multiple exist
        if not token:
            raw_cookie = request.headers.get('Cookie', '')
            if 'auth_token=' in raw_cookie:
                parts = [p.strip() for p in raw_cookie.split(';')]
                auth_tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
                if auth_tokens:
                    auth_token = auth_tokens[-1]

        print(f"Auth token for initiate-profile-assistant: {auth_token}")

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        # Verify period and add to enrollments
        period = period_service.verify_period_id(auth_token, period_id)
        return jsonify({"message": "Period verified and added to enrollments", "period": period}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except LookupError as le:
        return jsonify({"error": str(le)}), 404
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@period_bp.route('/unenroll', methods=['POST'])
def unenroll():
    try:
        auth_token = None
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            auth_token = token

        if not token:
            raw_cookie = request.headers.get('Cookie', '')
            if 'auth_token=' in raw_cookie:
                parts = [p.strip() for p in raw_cookie.split(';')]
                auth_tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
                if auth_tokens:
                    auth_token = auth_tokens[-1]

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_service.unenroll_from_period(auth_token, period_id)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except LookupError as le:
        return jsonify({"error": str(le)}), 404
    except Exception as e:
        print(f"Unexpected error in unenroll: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@period_bp.route('/initiate-ltg-conversation', methods=['POST'])
def initiate_ltg_conversation():
    try:
        
        
        # Prefer Authorization: Bearer <token>
        auth_token = None
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            auth_token = token


        # Fallback: parse the last auth_token from Cookie header if multiple exist
        if not token:
            raw_cookie = request.headers.get('Cookie', '')
            if 'auth_token=' in raw_cookie:
                parts = [p.strip() for p in raw_cookie.split(';')]
                auth_tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
                if auth_tokens:
                    auth_token = auth_tokens[-1]

        print(f"Auth token for initiate-profile-assistant: {auth_token}")

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        # You may want to pass auth_token and period_id to the service
        result = period_service.initiate_ltg_conversation(auth_token, period_id)
        return jsonify(result), 200

    except ValueError as ve:
        print(f"ValueError: {ve}")
        return jsonify({"error": str(ve)}), 400

    except LookupError as le:
        return jsonify({"error": str(le)}), 404

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@period_bp.route('/continue-ltg-conversation', methods=['POST'])
def continue_ltg_conversation():
    try:
        data = request.json
        
        
        # Prefer Authorization: Bearer <token>
        auth_token = None
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            auth_token = token


        # Fallback: parse the last auth_token from Cookie header if multiple exist
        if not token:
            raw_cookie = request.headers.get('Cookie', '')
            if 'auth_token=' in raw_cookie:
                parts = [p.strip() for p in raw_cookie.split(';')]
                auth_tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
                if auth_tokens:
                    auth_token = auth_tokens[-1]

        print(f"Auth token for continue-ltg-conversation: {auth_token}")

        conversation_type = data.get('conversation_type')
        conversation_id = data.get('conversation_id')
        user_message = data.get('message')
        period_id = data.get('period_id')  # Optional, helps with lookup

        if not conversation_type:
            return jsonify({"error": "conversation_type is required"}), 400
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400
        if not user_message:
            return jsonify({"error": "message is required"}), 400

        result = period_service.continue_ltg_conversation(
            auth_token, conversation_type, conversation_id, user_message, period_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Note: /initiate-schedules-agent has been removed. 
# Quest generation now uses the centralized period_schedule with teacher-selected quest_enabled_weeks.
# The /initiate-homework-agent endpoint handles both creating quest placeholders and generating homework.
    
@period_bp.route('/initiate-homework-agent', methods=['POST'])
def initiate_homework_agent():
    try:
        
        
            
        # Prefer Authorization: Bearer <token>
        auth_token = None
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            auth_token = token


        # Fallback: parse the last auth_token from Cookie header if multiple exist
        if not token:
            raw_cookie = request.headers.get('Cookie', '')
            if 'auth_token=' in raw_cookie:
                parts = [p.strip() for p in raw_cookie.split(';')]
                auth_tokens = [p.split('=', 1)[1] for p in parts if p.startswith('auth_token=')]
                if auth_tokens:
                    auth_token = auth_tokens[-1]

        print(f"Auth token for initiate-profile-assistant: {auth_token}")

        sessions = period_service.session_dao.get_sessions_by_auth_token(auth_token)
        if not sessions:
            return jsonify({"error": "Invalid auth token"}), 401
        caller_id = sessions[0]['user_id']

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        student_id = data.get('student_id')
        if student_id:
            # Parent/teacher path — verify caller owns the period
            period = period_service.period_dao.get_period_by_id(period_id)
            if not period:
                return jsonify({"error": "Period not found"}), 404
            if period.get("owner_id", period.get("teacher_id")) != caller_id:
                return jsonify({"error": "Not authorized to generate quests for this period"}), 403
        else:
            student_id = caller_id

        result = period_service.start_homework_agent(auth_token, student_id, period_id)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in initiate-homework-agent: {str(e)}")
        return jsonify({"error": str(e)}), 500


@period_bp.route('/accept-parent-invite', methods=['POST'])
@jwt_required()
def accept_parent_invite():
    """
    Student endpoint — accepts a parent invite code.
    Links the authenticated student to the parent who generated the code.
    Records vpc_verified_at for COPPA 2025 homeschool consent tracking.
    """
    try:
        student_id = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        code = data.get("code", "").strip().upper()
        if not code:
            return jsonify({"error": "Invite code is required"}), 400

        invite = _invite_dao.get_invite_by_code(code)
        if not invite:
            return jsonify({"error": "Invalid invite code"}), 404

        if invite.get("used"):
            return jsonify({"error": "Invite code has already been used"}), 410

        expires_at_str = invite.get("expires_at", "")
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid invite data"}), 500

        if datetime.now(timezone.utc) > expires_at:
            return jsonify({"error": "Invite code has expired"}), 410

        parent_id = invite.get("parent_id")
        parent = _parent_dao.get_parent_by_id(parent_id)
        if not parent:
            return jsonify({"error": "Parent account not found"}), 404

        linked_ids = parent.get("linked_student_ids") or []
        if student_id in linked_ids:
            return jsonify({"message": "Already linked to this parent"}), 200

        linked_ids.append(student_id)
        vpc_verified_at = datetime.now(timezone.utc).isoformat()
        _parent_dao.update_parent(parent_id, {
            "linked_student_ids": linked_ids,
            "vpc_verified_at": vpc_verified_at,  # COPPA 2025 homeschool VPC record
        })
        _invite_dao.mark_used(code)

        return jsonify({
            "message": "Successfully linked to parent account",
            "parent_id": parent_id,
            "vpc_verified_at": vpc_verified_at,
        }), 200

    except Exception as e:
        print(f"Error in accept-parent-invite: {e}")
        return jsonify({"error": "Internal server error"}), 500