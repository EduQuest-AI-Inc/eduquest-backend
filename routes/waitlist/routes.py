# routes/waitlist/routes.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from .WaitlistService import WaitlistService
import traceback
import sys

waitlist_bp = Blueprint('waitlist', __name__)
svc = WaitlistService()


@waitlist_bp.route('/join', methods=['POST'])
@jwt_required()
def join_pilot_waitlist():
    """
    Join the pilot study waitlist.
    Requires JWT authentication (teacher must be logged in).
    
    Request body (optional):
        - referralCode: Optional referral code from another teacher
    
    Returns:
        - success: Whether the join was successful
        - position: Position in the waitlist queue
        - referral_code: Teacher's referral code to share with others
        - status: Current status (pending/approved)
        - joined_at: Timestamp when joined
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        
        # Accept referralCode or referral_code from request body
        referral_code = data.get('referralCode') or data.get('referral_code')
        
        result = svc.join(user_id, referral_code)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return jsonify({"message": "Failed to join waitlist"}), 500


@waitlist_bp.route('/status', methods=['GET'])
@jwt_required()
def get_waitlist_status():
    """
    Get the current waitlist status for the logged-in teacher.
    
    Returns:
        - on_waitlist: Whether the teacher is on the waitlist
        - approved: Whether the teacher is approved for pilot access
        - position: Position in queue (if on waitlist)
        - referral_code: Teacher's referral code (if on waitlist)
        - status: Current status string
    """
    try:
        user_id = get_jwt_identity()
        result = svc.get_status(user_id)
        return jsonify(result), 200

    except Exception:
        traceback.print_exc(file=sys.stderr)
        return jsonify({"message": "Failed to get waitlist status"}), 500


@waitlist_bp.route('/approve/<user_id>', methods=['POST'])
@jwt_required()
def approve_teacher(user_id: str):
    """
    Approve a teacher for pilot study access.
    This is an admin-only endpoint (add proper admin check in production).
    
    Args:
        user_id: The teacher ID to approve
    
    Returns:
        - success: Whether the approval succeeded
    """
    try:
        # TODO: Add admin role check here
        # For now, just allow the operation
        result = svc.approve(user_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify({"message": "Failed to approve teacher", **result}), 400

    except Exception:
        traceback.print_exc(file=sys.stderr)
        return jsonify({"message": "Failed to approve teacher"}), 500
