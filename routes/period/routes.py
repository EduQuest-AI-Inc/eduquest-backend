import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .period_service import PeriodService
from utils.token_utils import extract_auth_token, get_user_id_from_token

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.parent_dao import ParentDAO
    from data_access.supabase.parent_invite_dao import ParentInviteDAO
else:
    from data_access.parent_dao import ParentDAO
    from data_access.parent_invite_dao import ParentInviteDAO

logger = logging.getLogger(__name__)

period_bp = Blueprint('period', __name__)
period_service = PeriodService()
_parent_dao = ParentDAO()
_invite_dao = ParentInviteDAO()


def _token():
    return extract_auth_token(request)


@period_bp.route('/my-periods', methods=['GET'])
def my_periods():
    try:
        result = period_service.get_my_periods(_token())
        return jsonify(result), 200
    except Exception as e:
        logger.error("Unexpected error in my-periods: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/verify-period', methods=['POST'])
def verify_period():
    try:
        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        period = period_service.verify_period_id(_token(), period_id)
        return jsonify({"message": "Period verified and added to enrollments", "period": period}), 200
    except Exception as e:
        logger.error("Unexpected error in verify-period: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/unenroll', methods=['POST'])
def unenroll():
    data = request.json
    period_id = data.get('period_id')
    if not period_id:
        return jsonify({"error": "period_id is required"}), 400
    result = period_service.unenroll_from_period(_token(), period_id)
    return jsonify(result), 200


@period_bp.route('/initiate-ltg-conversation', methods=['POST'])
def initiate_ltg_conversation():
    try:
        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        result = period_service.initiate_ltg_conversation(_token(), period_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Unexpected error in initiate-ltg-conversation: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/continue-ltg-conversation', methods=['POST'])
def continue_ltg_conversation():
    try:
        data = request.json
        conversation_type = data.get('conversation_type')
        conversation_id = data.get('conversation_id')
        user_message = data.get('message')
        period_id = data.get('period_id')

        if not conversation_type:
            return jsonify({"error": "conversation_type is required"}), 400
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400
        if not user_message:
            return jsonify({"error": "message is required"}), 400

        result = period_service.continue_ltg_conversation(
            _token(), conversation_type, conversation_id, user_message, period_id
        )
        return jsonify(result), 200
    except Exception as e:
        logger.error("Unexpected error in continue-ltg-conversation: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@period_bp.route('/initiate-homework-agent', methods=['POST'])
def initiate_homework_agent():
    try:
        auth_token = _token()
        caller_id = get_user_id_from_token(auth_token, period_service.session_dao)

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        user_id = data.get('user_id')
        if user_id:
            period = period_service.period_dao.get_period_by_id(period_id)
            if not period:
                return jsonify({"error": "Period not found"}), 404
            if period.get("owner_id", period.get("user_id")) != caller_id:
                return jsonify({"error": "Not authorized to generate quests for this period"}), 403
        else:
            user_id = caller_id

        result = period_service.start_homework_agent(auth_token, user_id, period_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error in initiate-homework-agent: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@period_bp.route('/accept-parent-invite', methods=['POST'])
@jwt_required()
def accept_parent_invite():
    try:
        user_id = get_jwt_identity()
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

        user_id = invite.get("user_id")
        parent = _parent_dao.get_parent_by_id(user_id)
        if not parent:
            return jsonify({"error": "Parent account not found"}), 404

        linked_ids = parent.get("linked_user_ids") or []
        if user_id in linked_ids:
            return jsonify({"message": "Already linked to this parent"}), 200

        linked_ids.append(user_id)
        vpc_verified_at = datetime.now(timezone.utc).isoformat()
        _parent_dao.update_parent(user_id, {
            "linked_user_ids": linked_ids,
            "vpc_verified_at": vpc_verified_at,
        })
        _invite_dao.mark_used(code)

        return jsonify({
            "message": "Successfully linked to parent account",
            "user_id": user_id,
            "vpc_verified_at": vpc_verified_at,
        }), 200

    except Exception as e:
        logger.error("Error in accept-parent-invite: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
