from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from routes.teacher.teacher_service import TeacherService
from openai import OpenAI
import boto3
import shutil
import tempfile, os
from assistants import create_class
from s3 import upload_file_to_s3

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

        # Save files to temp directory first
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            file_paths.append(file_path)

        print("Received files:", file_paths)

        vector_store = client.vector_stores.create(name=course)
        file_streams = [open(path, "rb") for path in file_paths]
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=file_streams
        )
        print("Uploaded files to vector store:", vector_store.id)

        # Check if OpenAI API key is available
        if not os.getenv("OPENAI_API_KEY"):
            print("WARNING: OPENAI_API_KEY not set. Skipping assistant creation.")
            update_assistant_id = "placeholder_update_assistant_id"
            ltg_assistant_id = "placeholder_ltg_assistant_id"
        else:
            class_instance = create_class(course)
            class_instance.vector_store = vector_store  
            
            class_instance.create_update_assistant()
            class_instance.create_ltg_assistant()
            
            update_assistant_id = class_instance.update_assistant.id
            ltg_assistant_id = class_instance.ltg_assistant.id

            #printing this for test only
            print("Created update assistant:", update_assistant_id)
            print("Created LTG assistant:", ltg_assistant_id)

        # Create the period first (this generates the actual period_id)
        period = teacher_service.create_period(
            course=course,
            teacher_id=teacher_id,
            vector_store_id=vector_store.id,
            file_urls=[]  # We'll update this after S3 uploads
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