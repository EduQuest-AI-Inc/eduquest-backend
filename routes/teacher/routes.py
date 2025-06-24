from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.teacher.teacher_service import TeacherService
from openai import OpenAI
import boto3
import shutil
import tempfile, os
from assistants import create_class
from s3 import upload_to_s3

teacher_bp = Blueprint("teacher", __name__)
teacher_service = TeacherService()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@teacher_bp.route("/create-period", methods=["POST"])
@jwt_required()
def create_period():
    try:
        course = request.form.get("course")
        files = request.files.getlist("files")
        
        if not course:
            return jsonify({"error": "Course name is required"}), 400

        teacher_id = get_jwt_identity()

        temp_dir = tempfile.mkdtemp()
        file_paths = []
        s3_urls = []

        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            file_paths.append(file_path)

            s3_url = upload_to_s3(file, folder=f"periods/{course}")  # Use course name for folder
            print("Uploaded to S3:", s3_url) #uploading to s3 as well.
            s3_urls.append(s3_url)

        print("Received files:", file_paths)

        vector_store = client.vector_stores.create(name=course)
        file_streams = [open(path, "rb") for path in file_paths]
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=file_streams
        )
        print("Uploaded files to vector store:", vector_store.id)

        class_instance = create_class(course)
        class_instance.vector_store = vector_store  
        
        class_instance.create_update_assistant()
        class_instance.create_ltg_assistant()
        
        update_assistant_id = class_instance.update_assistant.id
        ltg_assistant_id = class_instance.ltg_assistant.id

        #printing this for test only
        print("Created update assistant:", update_assistant_id)
        print("Created LTG assistant:", ltg_assistant_id)

        period = teacher_service.create_period(
            course=course,
            teacher_id=teacher_id,
            vector_store_id=vector_store.id,
            file_urls=[url for url in s3_urls if url is not None]
        )
        
        teacher_service.update_period_assistants(period['period_id'], update_assistant_id, ltg_assistant_id)
        
        # cleanup
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
        BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

        file_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return Response(
            file_obj['Body'].read(),
            content_type=file_obj['ContentType'],
            headers={"Content-Disposition": f"inline; filename={key.split('/')[-1]}"}
        )
    except Exception as e:
        print("Error retrieving file:", e)
        return jsonify({"error": "Failed to retrieve file"}), 500