import os
import shutil
import tempfile

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from openai import OpenAI

from routes.parent.parent_service import ParentService
from s3 import upload_file_to_s3

parent_bp = Blueprint("parent", __name__)
parent_service = ParentService()
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

        return jsonify({
            "message": "Class created successfully",
            "period": period,
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
