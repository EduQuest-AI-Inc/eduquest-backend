from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.teacher.teacher_service import TeacherService
from routes.teacher.period_schedule_service import PeriodScheduleService
from routes.waitlist.WaitlistService import WaitlistService
from data_access.teacher_dao import TeacherDAO
from openai import OpenAI
from canvasapi import Canvas
import boto3
import shutil
import tempfile, os
import json
from s3 import upload_file_to_s3
from canvas.canvas import Course as CanvasCourse, course_to_json

teacher_bp = Blueprint("teacher", __name__)
teacher_service = TeacherService()
period_schedule_service = PeriodScheduleService()
teacher_dao = TeacherDAO()
waitlist_service = WaitlistService()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@teacher_bp.route("/create-period", methods=["POST"])
@jwt_required()
def create_period():
    try:
        teacher_id = get_jwt_identity()
        
        # Check if pilot waitlist enforcement is enabled (default: true)
        pilot_waitlist_enabled = os.getenv("PILOT_WAITLIST_ENABLED", "true").lower() == "true"
        
        # Check if teacher is approved for pilot study (only enforce when waitlist is enabled)
        if pilot_waitlist_enabled:
            teacher = teacher_dao.get_teacher_by_id(teacher_id)
            if not teacher or not teacher.get("pilot_approved", False):
                waitlist_status = waitlist_service.get_status(teacher_id)
                return jsonify({
                    "error": "Pilot access required to create a class. Please join the pilot waitlist.",
                    "code": "PILOT_WAITLIST_REQUIRED",
                    "waitlist": waitlist_status,
                }), 403
        
        course = request.form.get("course")
        files = request.files.getlist("files")
        
        # Canvas integration fields (optional)
        canvas_api_url = request.form.get("canvas_api_url")
        canvas_api_key = request.form.get("canvas_api_key")
        canvas_course_id = request.form.get("canvas_course_id")
        canvas_course_name = request.form.get("canvas_course_name")
        
        if not course:
            return jsonify({"error": "Course name is required"}), 400

        temp_dir = tempfile.mkdtemp()
        file_paths = []

        # Save uploaded files to temp directory first
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            file_paths.append(file_path)

        print("Received files:", file_paths)

        # If Canvas course provided, parse it and add to file_paths
        if canvas_api_url and canvas_api_key and canvas_course_id:
            try:
                print(f"Parsing Canvas course: {canvas_course_id}")
                canvas_course = CanvasCourse(
                    int(canvas_course_id),
                    canvas_api_url,
                    canvas_api_key
                )
                canvas_json = course_to_json(canvas_course)
                
                # Write canvas course JSON to temp file
                canvas_file_path = os.path.join(temp_dir, "canvas_course.json")
                with open(canvas_file_path, "w") as f:
                    f.write(canvas_json)
                file_paths.append(canvas_file_path)
                print(f"Canvas course parsed and saved to: {canvas_file_path}")
            except Exception as canvas_error:
                print(f"Warning: Failed to parse Canvas course: {canvas_error}")
                # Continue without Canvas data rather than failing the whole request

        vector_store = client.vector_stores.create(name=course)
        file_streams = [open(path, "rb") for path in file_paths]
        if file_streams:
            client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=file_streams
            )
        print("Uploaded files to vector store:", vector_store.id)

        # Create the period (with Canvas fields if provided)
        period = teacher_service.create_period(
            course=course,
            teacher_id=teacher_id,
            vector_store_id=vector_store.id,
            file_urls=[],  # We'll update this after S3 uploads
            canvas_api_url=canvas_api_url,
            canvas_api_key=canvas_api_key,
            canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
            canvas_course_name=canvas_course_name
        )
        
        # Now upload files to S3 using the actual period_id
        period_id = period['period_id']
        s3_urls = []
        
        for file_path in file_paths:
            s3_url = upload_file_to_s3(file_path, folder=f"periods/{period_id}/course materials")
            if s3_url is None:
                print(f"WARNING: S3 upload failed for {os.path.basename(file_path)}. Check AWS credentials.")
                s3_url = f"local/{os.path.basename(file_path)}"  # Fallback for testing
            print(f"DEBUG: Uploaded to S3: {s3_url}")
            s3_urls.append(s3_url)

        print(f"DEBUG: All S3 URLs: {s3_urls}")
        print(f"DEBUG: Filtered S3 URLs: {[url for url in s3_urls if url is not None]}")

        # Update the period with the S3 URLs
        teacher_service.update_period_files(period_id, [url for url in s3_urls if url is not None])

        # cleanup
        for f in file_streams:
            f.close()
        shutil.rmtree(temp_dir)

        # Auto-generate schedule for the period
        schedule_result = None
        try:
            print(f"Auto-generating schedule for period {period_id}...")
            schedule_result = period_schedule_service.generate_and_save_schedule(
                period_id=period_id,
                teacher_id=teacher_id
            )
            print(f"Schedule generated successfully for period {period_id}")
        except Exception as schedule_error:
            print(f"Warning: Failed to auto-generate schedule: {schedule_error}")
            # Continue without schedule - teacher can generate later

        return jsonify({
            "message": "Period created successfully",
            "period": period,
            "schedule": schedule_result
        }), 201

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
    

@teacher_bp.route('/get-file/<path:key>', methods=['GET'])
@jwt_required()
def get_file(key):
    try:
        print(f"DEBUG: File download requested for key: {key}")
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION")
        )
        BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
        print(f"DEBUG: Using S3 bucket: {BUCKET_NAME}")

        file_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        print(f"DEBUG: Successfully retrieved file from S3")
        return Response(
            file_obj['Body'].read(),
            content_type=file_obj['ContentType'],
            headers={"Content-Disposition": f"inline; filename={key.split('/')[-1]}"}
        )
    except Exception as e:
        print(f"DEBUG: Error retrieving file: {e}")
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

        teacher_id = get_jwt_identity()

        period = teacher_service.get_period_by_id(period_id)
        if not period:
            return jsonify({"error": "Period not found"}), 404

        if period.get('teacher_id') != teacher_id:
            return jsonify({"error": "Unauthorized"}), 403

        course = period.get('course', 'unknown')
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        s3_urls = []

        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            file_paths.append(file_path)

            s3_url = upload_file_to_s3(file_path, folder=f"periods/{period_id}/course materials")
            if s3_url is None:
                print(f"WARNING: S3 upload failed for {file.filename}. Check AWS credentials.")
                s3_url = f"local/{file.filename}"  # Fallback for testing
            print(f"DEBUG: Uploaded to S3: {s3_url}")
            s3_urls.append(s3_url)

        print(f"DEBUG: All S3 URLs: {s3_urls}")
        print(f"DEBUG: Filtered S3 URLs: {[url for url in s3_urls if url is not None]}")

        existing_file_urls = period.get('file_urls', [])
        new_file_urls = [url for url in s3_urls if url is not None]
        updated_file_urls = existing_file_urls + new_file_urls

        teacher_service.update_period_files(period_id, updated_file_urls)

        shutil.rmtree(temp_dir)

        return jsonify({
            "message": f"Successfully added {len(new_file_urls)} files to period",
            "added_files": new_file_urls
        }), 200
    except Exception as e:
        print(f"Error in add_files_to_period: {e}")
        return jsonify({"error": "Failed to add files to period"}), 500


@teacher_bp.route("/canvas/courses", methods=["POST"])
@jwt_required()
def list_canvas_courses():
    """
    List courses from Canvas where the user has teacher-level access.
    Body: { api_url, api_key }
    Returns: [{ id, name }]
    """
    try:
        data = request.get_json()
        api_url = data.get("api_url")
        api_key = data.get("api_key")

        if not api_url or not api_key:
            return jsonify({"error": "api_url and api_key are required"}), 400

        # Connect to Canvas
        canvas = Canvas(api_url, api_key)

        # Get current user to filter courses by teacher enrollment
        current_user = canvas.get_current_user()

        # Get courses where user is a teacher/instructor
        courses = []
        for course in current_user.get_courses(enrollment_type="teacher"):
            try:
                courses.append({
                    "id": course.id,
                    "name": getattr(course, "name", f"Course {course.id}")
                })
            except Exception:
                # Some courses may not have all attributes accessible
                continue

        return jsonify({"courses": courses}), 200

    except Exception as e:
        print(f"Error listing Canvas courses: {e}")
        return jsonify({"error": f"Failed to connect to Canvas: {str(e)}"}), 400


# ============ Period Schedule Endpoints ============

@teacher_bp.route("/period-schedule/generate", methods=["POST"])
@jwt_required()
def generate_period_schedule():
    """
    Generate a schedule for a period.
    Body: { period_id }
    """
    try:
        teacher_id = get_jwt_identity()
        data = request.get_json()
        period_id = data.get("period_id")

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.generate_and_save_schedule(
            period_id=period_id,
            teacher_id=teacher_id
        )

        return jsonify({
            "message": "Schedule generated successfully",
            **result
        }), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        print(f"Error generating period schedule: {e}")
        return jsonify({"error": "Failed to generate schedule"}), 500


@teacher_bp.route("/period-schedule", methods=["GET"])
@jwt_required()
def get_period_schedule():
    """
    Get the schedule for a period.
    Query params: period_id
    """
    try:
        teacher_id = get_jwt_identity()
        period_id = request.args.get("period_id")

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.get_schedule(
            period_id=period_id,
            teacher_id=teacher_id
        )

        if result is None:
            return jsonify({"error": "No schedule found for this period"}), 404

        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        print(f"Error getting period schedule: {e}")
        return jsonify({"error": "Failed to get schedule"}), 500


@teacher_bp.route("/period-schedule", methods=["PUT"])
@jwt_required()
def update_period_schedule():
    """
    Update the schedule for a period (teacher edits).
    Body: { period_id, schedule: { weeks: [...] } }
    """
    try:
        teacher_id = get_jwt_identity()
        data = request.get_json()
        period_id = data.get("period_id")
        schedule = data.get("schedule")

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        if not schedule:
            return jsonify({"error": "schedule is required"}), 400

        result = period_schedule_service.update_schedule(
            period_id=period_id,
            teacher_id=teacher_id,
            schedule_dict=schedule
        )

        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        print(f"Error updating period schedule: {e}")
        return jsonify({"error": "Failed to update schedule"}), 500


@teacher_bp.route("/period-schedule/quest-weeks", methods=["PUT"])
@jwt_required()
def set_period_quest_weeks():
    """
    Set which weeks have quests enabled.
    Body: { period_id, quest_enabled_weeks: [1, 2, 5, ...] }
    """
    try:
        teacher_id = get_jwt_identity()
        data = request.get_json()
        period_id = data.get("period_id")
        quest_enabled_weeks = data.get("quest_enabled_weeks", [])

        if not period_id:
            return jsonify({"error": "period_id is required"}), 400
        if not isinstance(quest_enabled_weeks, list):
            return jsonify({"error": "quest_enabled_weeks must be a list"}), 400

        result = period_schedule_service.set_quest_weeks(
            period_id=period_id,
            teacher_id=teacher_id,
            quest_enabled_weeks=quest_enabled_weeks
        )

        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        print(f"Error setting quest weeks: {e}")
        return jsonify({"error": "Failed to set quest weeks"}), 500