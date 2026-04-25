import logging
import os
import shutil
import tempfile

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from .period_service import PeriodService
from .period_management_service import PeriodManagementService
from .period_file_helpers import (
    save_files_to_temp,
    append_canvas_file,
    create_vector_store,
    upload_period_files,
    try_generate_schedule,
    get_file_presigned_url,
)
from routes.parent.parent_service import ParentService
from .period_schedule_service import PeriodScheduleService
from routes.teacher.teacher_service import TeacherService
from routes.waitlist.WaitlistService import WaitlistService
from data_access.teacher_dao import TeacherDAO
from utils.token_utils import extract_auth_token
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from exceptions.auth_error import AuthError

logger = logging.getLogger(__name__)

period_bp = Blueprint('period', __name__)
period_service = PeriodService()
period_management_service = PeriodManagementService()
period_schedule_service = PeriodScheduleService()
parent_service = ParentService()
teacher_service = TeacherService()
teacher_dao = TeacherDAO()
waitlist_service = WaitlistService()


def _validate_pilot_access(user_id: str):
    """Return a 403 response tuple if the teacher lacks pilot access, else None."""
    pilot_waitlist_enabled = os.getenv("PILOT_WAITLIST_ENABLED", "true").lower() == "true"
    if not pilot_waitlist_enabled:
        return None
    teacher = teacher_dao.get_teacher_by_id(user_id)
    if not teacher or not teacher.get("pilot_approved", False):
        waitlist_status = waitlist_service.get_status(user_id)
        return jsonify({
            "error": "Pilot access required to create a class. Please join the pilot waitlist.",
            "code": "PILOT_WAITLIST_REQUIRED",
            "waitlist": waitlist_status,
        }), 403
    return None


# ─── Owner-facing period routes (teacher + parent) ────────────────────────────

@period_bp.route('/periods', methods=['GET'])
@jwt_required()
def list_periods():
    try:
        user_id = get_jwt_identity()
        result = period_management_service.get_periods_by_owner(user_id)
        return jsonify({"periods": result}), 200
    except Exception as e:
        logger.error("Unexpected error in list-periods: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


# ─── Student-facing period routes ─────────────────────────────────────────────

@period_bp.route('/my-periods', methods=['GET'])
@jwt_required()
def my_periods():
    try:
        user_id = get_jwt_identity()
        result = period_service.get_my_periods(user_id)
        return jsonify(result), 200
    except (ValidationError, NotFoundError, AuthError):
        raise
    except Exception as e:
        logger.error("Unexpected error in my-periods: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/verify-period', methods=['POST'])
@jwt_required()
def verify_period():
    try:
        user_id = get_jwt_identity()
        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        period = period_service.verify_period_id(user_id, period_id)
        return jsonify({"message": "Period verified and added to enrollments", "period": period}), 200
    except (ValidationError, NotFoundError, AuthError):
        raise
    except Exception as e:
        logger.error("Unexpected error in verify-period: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/unenroll', methods=['POST'])
@jwt_required()
def unenroll():
    try:
        user_id = get_jwt_identity()
        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        result = period_service.unenroll_from_period(user_id, period_id)
        return jsonify(result), 200
    except (ValidationError, NotFoundError, AuthError):
        raise
    except Exception as e:
        logger.error("Unexpected error in unenroll: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/initiate-ltg-conversation', methods=['POST'])
@jwt_required()
def initiate_ltg_conversation():
    try:
        user_id = get_jwt_identity()
        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        result = period_service.initiate_ltg_conversation(user_id, period_id)
        return jsonify(result), 200
    except (ValidationError, NotFoundError, AuthError):
        raise
    except Exception as e:
        logger.error("Unexpected error in initiate-ltg-conversation: %s", e, exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@period_bp.route('/continue-ltg-conversation', methods=['POST'])
@jwt_required()
def continue_ltg_conversation():
    try:
        user_id = get_jwt_identity()
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
            user_id, conversation_type, conversation_id, user_message, period_id
        )
        return jsonify(result), 200
    except (ValidationError, NotFoundError, AuthError):
        raise
    except Exception as e:
        logger.error("Unexpected error in continue-ltg-conversation: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@period_bp.route('/initiate-homework-agent', methods=['POST'])
@jwt_required()
def initiate_homework_agent():
    try:
        caller_id = get_jwt_identity()

        data = request.json
        period_id = data.get('period_id')
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        user_id = data.get('user_id')
        if user_id:
            period = period_service.period_dao.get_period_by_id(period_id)
            if not period:
                return jsonify({"error": "Period not found"}), 404
            if period.get("owner_id") != caller_id:
                return jsonify({"error": "Not authorized to generate quests for this period"}), 403
        else:
            user_id = caller_id

        result = period_service.start_homework_agent(user_id, period_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error in initiate-homework-agent: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ─── Accept parent invite ──────────────────────────────────────────────────────

@period_bp.route('/accept-parent-invite', methods=['POST'])
@jwt_required()
def accept_parent_invite():
    try:
        student_id = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        code = data.get("code", "").strip().upper()
        if not code:
            return jsonify({"error": "Invite code is required"}), 400

        result = parent_service.accept_invite(student_id, code)
        if result.get("already_linked"):
            return jsonify({"message": result["message"]}), 200
        return jsonify(result), 200

    except ValueError as ve:
        msg = str(ve)
        if "expired" in msg or "already been used" in msg:
            return jsonify({"error": msg}), 410
        if "not found" in msg.lower() or "invalid" in msg.lower():
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    except Exception as e:
        logger.error("Error in accept-parent-invite: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ─── Period creation (teacher + parent, unified) ───────────────────────────────

@period_bp.route('/create-period', methods=['POST'])
@jwt_required()
def create_period():
    try:
        user_id = get_jwt_identity()

        # Determine role — pilot gate applies only to teachers
        from data_access.session_dao import SessionDAO
        sessions = SessionDAO().get_sessions_by_auth_token(extract_auth_token(request))
        role = sessions[0].get("role") if sessions else "student"

        if role == "teacher":
            denied = _validate_pilot_access(user_id)
            if denied:
                return denied

        course = request.form.get("name")
        if not course:
            return jsonify({"error": "Course name is required"}), 400

        canvas_api_url = request.form.get("canvas_api_url") if role == "teacher" else None
        canvas_api_key = request.form.get("canvas_api_key") if role == "teacher" else None
        canvas_course_id = request.form.get("canvas_course_id") if role == "teacher" else None
        canvas_course_name = request.form.get("canvas_course_name") if role == "teacher" else None

        temp_dir = tempfile.mkdtemp()
        try:
            file_paths = save_files_to_temp(request.files.getlist("files"), temp_dir)
            if role == "teacher":
                append_canvas_file(temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id)

            vector_store, file_streams = create_vector_store(course, file_paths)

            period = period_management_service.create_period(
                course=course,
                user_id=user_id,
                vector_store_id=vector_store.id,
                file_urls=[],
                canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
                canvas_course_name=canvas_course_name,
            )

            period_id = period['period_id']
            s3_urls = upload_period_files(file_paths, period_id)
            period_management_service.update_file_urls(period_id, [u for u in s3_urls if u])

            for f in file_streams:
                f.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        schedule_result = try_generate_schedule(period_id, user_id)
        return jsonify({
            "message": "Period created successfully",
            "period": period,
            "schedule": schedule_result,
        }), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error in create-period: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ─── File access ───────────────────────────────────────────────────────────────

@period_bp.route('/get-file/<path:key>', methods=['GET'])
@jwt_required()
def get_file(key):
    try:
        url = get_file_presigned_url(key)
        return jsonify({"url": url}), 200
    except Exception as e:
        logger.error("Error generating presigned URL for %s: %s", key, e, exc_info=True)
        return jsonify({"error": "Failed to retrieve file"}), 500


@period_bp.route('/add-files-to-period', methods=['POST'])
@jwt_required()
def add_files_to_period():
    try:
        user_id = get_jwt_identity()
        period_id = request.form.get("period_id")
        files = request.files.getlist("files")

        if not period_id:
            return jsonify({"error": "Period ID is required"}), 400
        if not files:
            return jsonify({"error": "No files provided"}), 400

        period = period_management_service.get_period_by_id(period_id)
        if not period:
            return jsonify({"error": "Period not found"}), 404
        if period.get('owner_id') != user_id:
            return jsonify({"error": "Unauthorized"}), 403

        temp_dir = tempfile.mkdtemp()
        try:
            file_paths = save_files_to_temp(files, temp_dir)
            new_file_urls = [u for u in upload_period_files(file_paths, period_id) if u]
            period_management_service.update_file_urls(
                period_id, (period.get('file_urls') or []) + new_file_urls
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            "message": f"Successfully added {len(new_file_urls)} files to period",
            "added_files": new_file_urls,
        }), 200
    except Exception as e:
        logger.error("Error in add-files-to-period: %s", e, exc_info=True)
        return jsonify({"error": "Failed to add files to period"}), 500


# ─── Period schedule (owner-only; role-agnostic — PeriodScheduleService checks ownership) ──

@period_bp.route('/period-schedule/generate', methods=['POST'])
@jwt_required()
def generate_period_schedule():
    try:
        user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        period_id = data.get("period_id")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.generate_and_save_schedule(period_id=period_id, user_id=user_id)
        return jsonify({"message": "Schedule generated successfully", **result}), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error generating period schedule: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to generate schedule: {e}"}), 500


@period_bp.route('/period-schedule', methods=['GET'])
@jwt_required()
def get_period_schedule():
    try:
        user_id = get_jwt_identity()
        period_id = request.args.get("period_id")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.get_schedule(period_id=period_id, user_id=user_id)
        if result is None:
            return jsonify({"error": "No schedule found for this period"}), 404
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error getting period schedule: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get schedule"}), 500


@period_bp.route('/period-schedule', methods=['PUT'])
@jwt_required()
def update_period_schedule():
    try:
        user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        period_id = data.get("period_id")
        schedule = data.get("schedule")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        if not schedule:
            return jsonify({"error": "schedule is required"}), 400

        result = period_schedule_service.update_schedule(period_id=period_id, user_id=user_id, schedule_dict=schedule)
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error updating period schedule: %s", e, exc_info=True)
        return jsonify({"error": "Failed to update schedule"}), 500


@period_bp.route('/period-schedule/quest-weeks', methods=['PUT'])
@jwt_required()
def set_period_quest_weeks():
    try:
        user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        period_id = data.get("period_id")
        quest_enabled_weeks = data.get("quest_enabled_weeks")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        if quest_enabled_weeks is None or not isinstance(quest_enabled_weeks, list):
            return jsonify({"error": "quest_enabled_weeks must be a list"}), 400

        result = period_schedule_service.set_quest_weeks(
            period_id=period_id, user_id=user_id, quest_enabled_weeks=quest_enabled_weeks
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error setting quest weeks: %s", e, exc_info=True)
        return jsonify({"error": "Failed to set quest weeks"}), 500
