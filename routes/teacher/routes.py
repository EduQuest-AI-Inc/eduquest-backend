from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.teacher.teacher_service import TeacherService
from openai import OpenAI
import shutil
import tempfile, os

teacher_bp = Blueprint("teacher", __name__)
teacher_service = TeacherService()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@teacher_bp.route("/create-period", methods=["POST"])
@jwt_required()
def create_period():
    try:
        period_id = request.form.get("period_id")
        course = request.form.get("course")
        files = request.files.getlist("files")
        
        if not period_id or not course:
            return jsonify({"error": "Missing required fields"}), 400

        teacher_id = get_jwt_identity()

        temp_dir = tempfile.mkdtemp()
        file_paths = []

        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            file_paths.append(file_path)

        print("Received files:", file_paths)

        period = teacher_service.create_period(
            period_id=period_id,
            course=course,
            teacher_id=teacher_id
        )

        vector_store_id = period['vector_store_id']

        file_streams = [open(path, "rb") for path in file_paths]
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store_id,
            files=file_streams
        )

        #printing this for test only
        print("Uploaded files to vector store:", vector_store_id)

        #file cleanup just in case
        for f in file_streams:
             f.close()
             shutil.rmtree(temp_dir)


        return jsonify({
            "message": "Period created successfully",
            "period": period
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

