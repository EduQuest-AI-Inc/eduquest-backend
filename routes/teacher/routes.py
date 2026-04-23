import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from canvasapi import Canvas

from routes.teacher.teacher_service import TeacherService

logger = logging.getLogger(__name__)
teacher_bp = Blueprint("teacher", __name__)
teacher_service = TeacherService()


@teacher_bp.route("/periods", methods=["GET"])
@jwt_required()
def periods():
    try:
        user_id = get_jwt_identity()
        result = teacher_service.get_periods_by_teacher(user_id)
        return jsonify({"periods": result}), 200
    except Exception as e:
        logger.error("Error in get_teacher_periods: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@teacher_bp.route("/canvas/courses", methods=["POST"])
@jwt_required()
def list_canvas_courses():
    """List courses from Canvas where the user has teacher-level access."""
    try:
        data = request.get_json()
        api_url = data.get("api_url")
        api_key = data.get("api_key")

        if not api_url or not api_key:
            return jsonify({"error": "api_url and api_key are required"}), 400

        canvas = Canvas(api_url, api_key)
        current_user = canvas.get_current_user()
        courses = []
        for course in current_user.get_courses(enrollment_type="teacher"):
            try:
                courses.append({
                    "id": course.id,
                    "name": getattr(course, "name", f"Course {course.id}")
                })
            except Exception:
                continue

        return jsonify({"courses": courses}), 200

    except Exception as e:
        logger.error("Error listing Canvas courses: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to connect to Canvas: {str(e)}"}), 400
