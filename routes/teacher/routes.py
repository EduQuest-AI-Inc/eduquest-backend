import logging
import os
import shutil
import tempfile

import boto3
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from openai import OpenAI
from canvasapi import Canvas

from routes.teacher.teacher_service import TeacherService
from routes.teacher.period_schedule_service import PeriodScheduleService
from routes.waitlist.WaitlistService import WaitlistService

if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.teacher_dao import TeacherDAO
else:
    from data_access.teacher_dao import TeacherDAO
from services.s3_service import upload_file_to_s3
from services.canvas_service import Course as CanvasCourse, course_to_json

logger = logging.getLogger(__name__)
teacher_bp = Blueprint("teacher", __name__)
teacher_service = TeacherService()
period_schedule_service = PeriodScheduleService()
teacher_dao = TeacherDAO()
waitlist_service = WaitlistService()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _validate_pilot_access(user_id):
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


def _save_files_to_temp(files):
    """Save uploaded file objects to a temp directory. Returns (temp_dir, file_paths)."""
    temp_dir = tempfile.mkdtemp()
    file_paths = []
    for file in files:
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        file_paths.append(file_path)
    return temp_dir, file_paths


def _append_canvas_file(temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id):
    """Fetch Canvas course data and append a JSON file to file_paths if credentials are present."""
    if not (canvas_api_url and canvas_api_key and canvas_course_id):
        return
    try:
        canvas_course = CanvasCourse(int(canvas_course_id), canvas_api_url, canvas_api_key)
        canvas_json = course_to_json(canvas_course)
        canvas_file_path = os.path.join(temp_dir, "canvas_course.json")
        with open(canvas_file_path, "w") as f:
            f.write(canvas_json)
        file_paths.append(canvas_file_path)
    except Exception as canvas_error:
        logger.warning("Failed to parse Canvas course: %s", canvas_error)


def _create_vector_store(course, file_paths):
    """Create an OpenAI vector store and upload files. Returns (vector_store, file_streams)."""
    vector_store = client.vector_stores.create(name=course)
    file_streams = [open(path, "rb") for path in file_paths]
    if file_streams:
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=file_streams,
        )
    return vector_store, file_streams


def _upload_period_files(file_paths, period_id):
    """Upload file_paths to S3 under the period folder. Returns list of URLs."""
    s3_urls = []
    for file_path in file_paths:
        s3_url = upload_file_to_s3(file_path, folder=f"periods/{period_id}/course materials")
        if s3_url is None:
            logger.warning("S3 upload failed for %s", os.path.basename(file_path))
            s3_url = f"local/{os.path.basename(file_path)}"
        s3_urls.append(s3_url)
    return s3_urls


def _try_generate_schedule(period_id, user_id):
    """Attempt schedule generation; log and return None on failure."""
    try:
        result = period_schedule_service.generate_and_save_schedule(
            period_id=period_id,
            user_id=user_id,
        )
        logger.info("Schedule generated successfully for period %s", period_id)
        return result
    except Exception as schedule_error:
        logger.warning("Failed to auto-generate schedule: %s", schedule_error)
        return None


@teacher_bp.route("/create-period", methods=["POST"])
@jwt_required()
def create_period():
    try:
        user_id = get_jwt_identity()
        denied = _validate_pilot_access(user_id)
        if denied:
            return denied

        course = request.form.get("course")
        if not course:
            return jsonify({"error": "Course name is required"}), 400

        canvas_api_url = request.form.get("canvas_api_url")
        canvas_api_key = request.form.get("canvas_api_key")
        canvas_course_id = request.form.get("canvas_course_id")
        canvas_course_name = request.form.get("canvas_course_name")

        temp_dir, file_paths = _save_files_to_temp(request.files.getlist("files"))
        _append_canvas_file(temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id)
        vector_store, file_streams = _create_vector_store(course, file_paths)

        period = teacher_service.create_period(
            course=course,
            user_id=user_id,
            vector_store_id=vector_store.id,
            file_urls=[],
            canvas_api_url=canvas_api_url,
            canvas_api_key=canvas_api_key,
            canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
            canvas_course_name=canvas_course_name,
        )

        period_id = period['period_id']
        s3_urls = _upload_period_files(file_paths, period_id)
        teacher_service.update_period_files(period_id, [u for u in s3_urls if u is not None])

        for f in file_streams:
            f.close()
        shutil.rmtree(temp_dir)

        schedule_result = _try_generate_schedule(period_id, user_id)
        return jsonify({
            "message": "Period created successfully",
            "period": period,
            "schedule": schedule_result,
        }), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error("Error in create_period: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@teacher_bp.route("/periods", methods=["GET"])
@jwt_required()
def periods():
    try:
        user_id = get_jwt_identity()
        result = teacher_service.get_periods_by_teacher(user_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Error in get_teacher_periods: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@teacher_bp.route('/get-file/<path:key>', methods=['GET'])
@jwt_required()
def get_file(key):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION")
        )
        bucket_name = os.getenv("S3_BUCKET_NAME")
        file_obj = s3.get_object(Bucket=bucket_name, Key=key)
        return Response(
            file_obj['Body'].read(),
            content_type=file_obj['ContentType'],
            headers={"Content-Disposition": f"inline; filename={key.split('/')[-1]}"}
        )
    except Exception as e:
        logger.error("Error retrieving file %s: %s", key, e, exc_info=True)
        return jsonify({"error": "Failed to retrieve file"}), 500


@teacher_bp.route("/add-files-to-period", methods=["POST"])
@jwt_required()
def add_files_to_period():
    try:
        period_id = request.form.get("period_id")
        files = request.files.getlist("files")

        if not period_id:
            return jsonify({"error": "Period ID is required"}), 400
        if not files:
            return jsonify({"error": "No files provided"}), 400

        user_id = get_jwt_identity()
        period = teacher_service.get_period_by_id(period_id)
        if not period:
            return jsonify({"error": "Period not found"}), 404
        if period.get('owner_id', period.get('user_id')) != user_id:
            return jsonify({"error": "Unauthorized"}), 403

        temp_dir, file_paths = _save_files_to_temp(files)
        new_file_urls = [u for u in _upload_period_files(file_paths, period_id) if u is not None]
        teacher_service.update_period_files(period_id, period.get('file_urls', []) + new_file_urls)
        shutil.rmtree(temp_dir)

        return jsonify({
            "message": f"Successfully added {len(new_file_urls)} files to period",
            "added_files": new_file_urls,
        }), 200
    except Exception as e:
        logger.error("Error in add_files_to_period: %s", e, exc_info=True)
        return jsonify({"error": "Failed to add files to period"}), 500


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


# ============ Period Schedule Endpoints ============

@teacher_bp.route("/period-schedule/generate", methods=["POST"])
@jwt_required()
def generate_period_schedule():
    """Generate a schedule for a period."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        period_id = data.get("period_id")

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.generate_and_save_schedule(
            period_id=period_id,
            user_id=user_id
        )
        return jsonify({"message": "Schedule generated successfully", **result}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.error("Error generating period schedule: %s", e, exc_info=True)
        return jsonify({"error": "Failed to generate schedule"}), 500


@teacher_bp.route("/period-schedule", methods=["GET"])
@jwt_required()
def get_period_schedule():
    """Get the schedule for a period."""
    try:
        user_id = get_jwt_identity()
        period_id = request.args.get("period_id")

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.get_schedule(period_id=period_id, user_id=user_id)
        if result is None:
            return jsonify({"error": "No schedule found for this period"}), 404
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.error("Error getting period schedule: %s", e, exc_info=True)
        return jsonify({"error": "Failed to get schedule"}), 500


@teacher_bp.route("/period-schedule", methods=["PUT"])
@jwt_required()
def update_period_schedule():
    """Update the schedule for a period (teacher edits)."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        period_id = data.get("period_id")
        schedule = data.get("schedule")

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        if not schedule:
            return jsonify({"error": "schedule is required"}), 400

        result = period_schedule_service.update_schedule(
            period_id=period_id,
            user_id=user_id,
            schedule_dict=schedule
        )
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.error("Error updating period schedule: %s", e, exc_info=True)
        return jsonify({"error": "Failed to update schedule"}), 500


@teacher_bp.route("/period-schedule/quest-weeks", methods=["PUT"])
@jwt_required()
def set_period_quest_weeks():
    """Set which weeks have quests enabled."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        period_id = data.get("period_id")
        quest_enabled_weeks = data.get("quest_enabled_weeks", [])

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        if not isinstance(quest_enabled_weeks, list):
            return jsonify({"error": "quest_enabled_weeks must be a list"}), 400

        result = period_schedule_service.set_quest_weeks(
            period_id=period_id,
            user_id=user_id,
            quest_enabled_weeks=quest_enabled_weeks
        )
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.error("Error setting quest weeks: %s", e, exc_info=True)
        return jsonify({"error": "Failed to set quest weeks"}), 500
