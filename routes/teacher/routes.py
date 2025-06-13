from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.teacher.teacher_service import TeacherService

teacher_bp = Blueprint("teacher", __name__)
teacher_service = TeacherService()

@teacher_bp.route("/create-period", methods=["POST"])
@jwt_required()
def create_period():
    try:
        data = request.get_json()

        required_fields = ["period_id", "course"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400

        teacher_id = get_jwt_identity()

        period = teacher_service.create_period(
            period_id=data["period_id"],
            course=data["course"],
            teacher_id=teacher_id
        )

        return jsonify({"message": "Period created successfully", "period": period}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        print(f"Error in create_period: {e}")
        return jsonify({"error": "Internal server error"}), 500

@teacher_bp.route("/periods", methods=["GET"])
@jwt_required()
def periods():
    try:
        teacher_id = get_jwt_identity()
        periods = teacher_service.get_periods_by_teacher(teacher_id)

        return jsonify(periods), 200

    except Exception as e:
        print(f"Error in get_teacher_periods: {e}")
        return jsonify({"error": "Internal server error"}), 500

