import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.enrollment.enrollment_service import EnrollmentService
from data_access.period_dao import PeriodDAO

logger = logging.getLogger(__name__)
enrollment_bp = Blueprint('enrollment', __name__)
service = EnrollmentService()
_period_dao = PeriodDAO()


@enrollment_bp.route('/enroll', methods=['POST'])
@jwt_required()
def enroll():
    try:
        user_id = get_jwt_identity()
        data = request.json
        period_id = data.get("period_id")
        semester = data.get("semester", "Fall 2025")
        result = service.enroll_student(user_id, period_id, semester)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Enrollment error: %s", e, exc_info=True)
        return jsonify({"error": "Server error"}), 500


@enrollment_bp.route('/enrollments/<period_id>', methods=['GET'])
@jwt_required()
def get_enrollments(period_id):
    try:
        caller_id = get_jwt_identity()
        period = _period_dao.get_period_by_id(period_id)
        if not period:
            return jsonify({"error": "Period not found"}), 404
        if period.get("owner_id") != caller_id:
            return jsonify({"error": "Not authorized"}), 403
        enrollments = service.get_enrollments_for_period(period_id)
        return jsonify(enrollments), 200
    except Exception as e:
        logger.error("Error fetching enrollments: %s", e, exc_info=True)
        return jsonify({"error": "Failed to fetch enrollments"}), 500


@enrollment_bp.route('/student-profile/<period_id>/<user_id>', methods=['GET'])
@jwt_required()
def get_student_profile(period_id, user_id):
    try:
        caller_id = get_jwt_identity()
        period = _period_dao.get_period_by_id(period_id)
        if not period:
            return jsonify({"error": "Period not found"}), 404
        if period.get("owner_id") != caller_id:
            return jsonify({"error": "Not authorized"}), 403
        profile = service.get_student_profile(period_id, user_id)
        if profile:
            return jsonify(profile), 200
        return jsonify({"error": "Profile not found"}), 404
    except Exception as e:
        logger.error("Error fetching student profile: %s", e, exc_info=True)
        return jsonify({"error": "Server error"}), 500
