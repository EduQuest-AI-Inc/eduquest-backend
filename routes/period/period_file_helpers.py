"""Shared helpers for period file handling (used by teacher and parent create-period flows)."""
import logging
import os

import boto3
from openai import OpenAI

from services.s3_service import upload_file_to_s3
from services.canvas_service import Course as CanvasCourse, course_to_json
from routes.teacher.period_schedule_service import PeriodScheduleService

logger = logging.getLogger(__name__)
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_period_schedule_service = PeriodScheduleService()


def save_files_to_temp(files, temp_dir: str) -> list:
    """Save uploaded file objects to temp_dir. Returns list of saved file paths."""
    file_paths = []
    for file in files:
        if file and file.filename:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            file_paths.append(file_path)
    return file_paths


def append_canvas_file(temp_dir: str, file_paths: list, canvas_api_url, canvas_api_key, canvas_course_id) -> None:
    """Fetch Canvas course data and append a JSON file to file_paths if credentials present."""
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


def create_vector_store(course: str, file_paths: list):
    """Create an OpenAI vector store, upload files. Returns (vector_store, file_streams)."""
    vector_store = _client.vector_stores.create(name=course)
    file_streams = [open(path, "rb") for path in file_paths]
    if file_streams:
        _client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=file_streams,
        )
    return vector_store, file_streams


def upload_period_files(file_paths: list, period_id: str) -> list:
    """Upload file_paths to S3 under the period folder. Returns list of URLs."""
    s3_urls = []
    for file_path in file_paths:
        s3_url = upload_file_to_s3(file_path, folder=f"periods/{period_id}/course materials")
        if s3_url is None:
            logger.warning("S3 upload failed for %s", os.path.basename(file_path))
            s3_url = f"local/{os.path.basename(file_path)}"
        s3_urls.append(s3_url)
    return s3_urls


def try_generate_schedule(period_id: str, user_id: str):
    """Attempt schedule generation; log and return None on failure."""
    try:
        result = _period_schedule_service.generate_and_save_schedule(
            period_id=period_id,
            user_id=user_id,
        )
        logger.info("Schedule generated successfully for period %s", period_id)
        return result
    except Exception as schedule_error:
        logger.warning("Failed to auto-generate schedule for %s: %s", period_id, schedule_error)
        return None


def get_file_presigned_url(key: str) -> str:
    """Return a presigned S3 URL for the given object key."""
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )
    bucket_name = os.getenv("S3_BUCKET_NAME")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=3600,
    )
    return url
