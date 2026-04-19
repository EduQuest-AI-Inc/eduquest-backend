import os
import shutil
import tempfile

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from openai import OpenAI

from routes.parent.parent_service import ParentService
from routes.teacher.period_schedule_service import PeriodScheduleService
from services.s3_service import upload_file_to_s3

# #region debug log
import json as _dbg_json
import time as _dbg_time
import traceback as _dbg_tb
_DBG_PATH = "/Users/goldenhuang/Desktop/EduQuest/.cursor/debug-f19ec3.log"
def _dbg(hypothesis_id, location, message, data):
    try:
        with open(_DBG_PATH, "a") as _f:
            _f.write(_dbg_json.dumps({
                "sessionId": "f19ec3",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(_dbg_time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
# #endregion

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
            print(f"Auto-generating schedule for parent period {period_id}...")
            schedule_result = period_schedule_service.generate_and_save_schedule(
                period_id=period_id,
                teacher_id=parent_id
            )
            print(f"Schedule generated successfully for parent period {period_id}")
        except Exception as schedule_error:
            print(f"Warning: Failed to auto-generate schedule for parent period: {schedule_error}")

        return jsonify({
            "message": "Class created successfully",
            "period": period,
            "schedule": schedule_result,
        }), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        print(f"Error creating parent period: {e}")
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
        print(f"Error fetching parent periods: {e}")
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
        print(f"Error generating invite: {e}")
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
        print(f"Error fetching linked students: {e}")
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
        # #region debug log
        _dbg("H2", "routes/parent/routes.py:generate_period_schedule", "entry", {
            "parent_id": parent_id, "period_id": period_id, "body_keys": list(body.keys()),
        })
        # #endregion
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
        # #region debug log
        _dbg("H2", "routes/parent/routes.py:generate_period_schedule", "exception", {
            "exc_type": type(e).__name__,
            "exc_str": str(e),
            "traceback_tail": _dbg_tb.format_exc()[-2000:],
        })
        # #endregion
        print(f"Error generating parent schedule: {e}")
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/period-schedule", methods=["GET"])
@jwt_required()
def get_period_schedule():
    """Return the schedule for a parent-owned period."""
    try:
        parent_id = get_jwt_identity()
        period_id = request.args.get("period_id")
        # #region debug log
        _dbg("H1", "routes/parent/routes.py:get_period_schedule", "entry", {
            "parent_id": parent_id,
            "request_url": request.url,
            "request_path": request.path,
            "request_query_string": request.query_string.decode("utf-8", errors="replace"),
            "arg_period_id": period_id,
            "all_args": dict(request.args),
        })
        # #endregion
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
        print(f"Error fetching parent schedule: {e}")
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
        print(f"Error updating parent schedule: {e}")
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
        print(f"Error setting quest weeks for parent: {e}")
        return jsonify({"error": "Internal server error"}), 500
