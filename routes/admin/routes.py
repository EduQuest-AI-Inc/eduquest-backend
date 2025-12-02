from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.admin.admin_service import AdminService

admin_bp = Blueprint("admin", __name__)
admin_service = AdminService()

@admin_bp.route("/classes", methods=["GET"])
@jwt_required()
def get_all_classes():
    try:
        admin_id = get_jwt_identity()
        classes = admin_service.get_all_classes(admin_id)
        return jsonify(classes), 200
    except Exception as e:
        print(f"Error in get_all_classes: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/students", methods=["GET"])
@jwt_required()
def get_all_students():
    try:
        admin_id = get_jwt_identity()
        students = admin_service.get_all_students(admin_id)
        return jsonify(students), 200
    except Exception as e:
        print(f"Error in get_all_students: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/students/<student_id>", methods=["GET"])
@jwt_required()
def get_student_detail(student_id):
    try:
        admin_id = get_jwt_identity()
        student_detail = admin_service.get_student_detail(admin_id, student_id)
        return jsonify(student_detail), 200
    except Exception as e:
        print(f"Error in get_student_detail: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/guardrail-flags", methods=["GET"])
@jwt_required()
def get_guardrail_flags():
    try:
        admin_id = get_jwt_identity()
        resolved = request.args.get("resolved")

        if resolved is not None:
            resolved = resolved.lower() == "true"

        flags = admin_service.get_guardrail_flags(admin_id, resolved)
        return jsonify(flags), 200
    except Exception as e:
        print(f"Error in get_guardrail_flags: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/guardrail-flags/<flag_id>/resolve", methods=["POST"])
@jwt_required()
def resolve_guardrail_flag(flag_id):
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        admin_notes = data.get("admin_notes")

        result = admin_service.resolve_guardrail_flag(admin_id, flag_id, admin_notes)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in resolve_guardrail_flag: {e}")
        return jsonify({"error": str(e)}), 500
