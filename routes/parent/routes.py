import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from routes.parent.parent_service import ParentService

logger = logging.getLogger(__name__)

parent_bp = Blueprint("parent", __name__)
parent_service = ParentService()


@parent_bp.route("/my-periods", methods=["GET"])
@jwt_required()
def my_periods():
    """Return all homeschool classes owned by the authenticated parent."""
    try:
        user_id = get_jwt_identity()
        periods = parent_service.get_periods_by_parent(user_id)
        return jsonify({"periods": periods}), 200
    except Exception as e:
        logger.error("Error fetching parent periods: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/generate-invite", methods=["POST"])
@jwt_required()
def generate_invite():
    """Generate a single-use 8-character invite code that expires in 24 hours."""
    try:
        user_id = get_jwt_identity()
        invite = parent_service.generate_invite(user_id)
        return jsonify(invite), 201
    except Exception as e:
        logger.error("Error generating invite: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/students", methods=["GET"])
@jwt_required()
def get_students():
    """Return student profiles for all students linked to this parent."""
    try:
        user_id = get_jwt_identity()
        students = parent_service.get_linked_students(user_id)
        return jsonify({"students": students}), 200
    except Exception as e:
        logger.error("Error fetching linked students: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

