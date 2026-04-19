import logging
import os
import shutil
import tempfile

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from openai import OpenAI

from routes.parent.parent_service import ParentService
from routes.teacher.period_schedule_service import PeriodScheduleService
from services.s3_service import upload_file_to_s3

logger = logging.getLogger(__name__)
parent_bp = Blueprint("parent", __name__)
parent_service = ParentService()
period_schedule_service = PeriodScheduleService()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@parent_bp.route("/create-period", methods=["POST"])
@jwt_required()
def create_period():
    """
    Create a homeschool class owned by the authenticated parent.
    Multipart form: course (required), files[] (optional PDFs/docs).
    No Canvas integration, no pilot gate.
    """
    try:
        parent_id = get_jwt_identity()

        course = request.form.get("course")
        files = request.files.getlist("files")

        if not course:
            return jsonify({"error": "Course name is required"}), 400

        temp_dir = tempfile.mkdtemp()
        file_paths = []

        for file in files:
            if file and file.filename:
                file_path = os.path.join(temp_dir, file.filename)
                file.save(file_path)
                file_paths.append(file_path)

        vector_store = client.vector_stores.create(name=course)
        file_streams = [open(path, "rb") for path in file_paths]
        if file_streams:
            client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=file_streams
            )

        period = parent_service.create_period(
            course=course,
            parent_id=parent_id,
            vector_store_id=vector_store.id,
            file_urls=[],
        )

        period_id = period["period_id"]
        s3_urls = []
        for file_path in file_paths:
            s3_url = upload_file_to_s3(file_path, folder=f"periods/{period_id}/course materials")
            if s3_url is None:
                s3_url = f"local/{os.path.basename(file_path)}"
            s3_urls.append(s3_url)

        if s3_urls:
            parent_service.update_period_files(period_id, s3_urls)

        for f in file_streams:
            f.close()
        shutil.rmtree(temp_dir)

        # Auto-generate schedule for the period (non-blocking; failures are logged)
        schedule_result = None
        try:
            schedule_result = period_schedule_service.generate_and_save_schedule(
                period_id=period_id,
                teacher_id=parent_id
            )
            logger.info("Schedule generated successfully for parent period %s", period_id)
        except Exception as schedule_error:
            logger.warning("Failed to auto-generate schedule for parent period %s: %s", period_id, schedule_error)

        return jsonify({
            "message": "Class created successfully",
            "period": period,
            "schedule": schedule_result,
        }), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error creating parent period: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/my-periods", methods=["GET"])
@jwt_required()
def my_periods():
    """Return all homeschool classes owned by the authenticated parent."""
    try:
        parent_id = get_jwt_identity()
        periods = parent_service.get_periods_by_parent(parent_id)
        return jsonify({"periods": periods}), 200
    except Exception as e:
        logger.error("Error fetching parent periods: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/generate-invite", methods=["POST"])
@jwt_required()
def generate_invite():
    """
    Generate a single-use 8-character invite code that expires in 24 hours.
    The student enters this code to link their account to this parent.
    """
    try:
        parent_id = get_jwt_identity()
        invite = parent_service.generate_invite(parent_id)
        return jsonify(invite), 201
    except Exception as e:
        logger.error("Error generating invite: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/students", methods=["GET"])
@jwt_required()
def get_students():
    """
    Return student profiles for all students linked to this parent.
    Audit-logged per SOC 2 / Rule 6.
    """
    try:
        parent_id = get_jwt_identity()
        students = parent_service.get_linked_students(parent_id)
        return jsonify({"students": students}), 200
    except Exception as e:
        logger.error("Error fetching linked students: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ─── Schedule endpoints ───────────────────────────────────────────────────────

@parent_bp.route("/period-schedule/generate", methods=["POST"])
@jwt_required()
def generate_period_schedule():
    """Generate (or regenerate) the AI schedule for a parent-owned period."""
    try:
        parent_id = get_jwt_identity()
        body = request.get_json(silent=True) or {}
        period_id = body.get("period_id")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.generate_and_save_schedule(
            period_id=period_id,
            teacher_id=parent_id
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error generating parent schedule: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/period-schedule", methods=["GET"])
@jwt_required()
def get_period_schedule():
    """Return the schedule for a parent-owned period."""
    try:
        parent_id = get_jwt_identity()
        period_id = request.args.get("period_id")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.get_schedule(
            period_id=period_id,
            teacher_id=parent_id
        )
        if result is None:
            return jsonify({"error": "No schedule found for this period"}), 404
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error fetching parent schedule: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/period-schedule", methods=["PUT"])
@jwt_required()
def update_period_schedule():
    """Save manual edits to the schedule for a parent-owned period."""
    try:
        parent_id = get_jwt_identity()
        body = request.get_json(silent=True) or {}
        period_id = body.get("period_id")
        schedule_dict = body.get("schedule")
        if not period_id or not schedule_dict:
            return jsonify({"error": "period_id and schedule are required"}), 400

        result = period_schedule_service.update_schedule(
            period_id=period_id,
            teacher_id=parent_id,
            schedule_dict=schedule_dict
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error updating parent schedule: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/period-schedule/quest-weeks", methods=["PUT"])
@jwt_required()
def set_quest_weeks():
    """Set which weeks have quests enabled for a parent-owned period."""
    try:
        parent_id = get_jwt_identity()
        body = request.get_json(silent=True) or {}
        period_id = body.get("period_id")
        quest_enabled_weeks = body.get("quest_enabled_weeks")
        if not period_id or quest_enabled_weeks is None:
            return jsonify({"error": "period_id and quest_enabled_weeks are required"}), 400

        result = period_schedule_service.set_quest_weeks(
            period_id=period_id,
            teacher_id=parent_id,
            quest_enabled_weeks=quest_enabled_weeks
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error setting quest weeks for parent: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
