import logging
import os

from integrations.canvas_service import Course as CanvasCourse, course_to_json
from integrations.s3_service import upload_file_to_s3
from integrations import openai_vector_store
from integrations.pdf_processor import preprocess_pdf
from services.period.period_schedule_service import PeriodScheduleService

logger = logging.getLogger(__name__)


class PeriodFileService:
    def __init__(self) -> None:
        self._schedule_service = PeriodScheduleService()

    def append_canvas_data(
        self,
        temp_dir: str,
        file_paths: list,
        canvas_api_url,
        canvas_api_key,
        canvas_course_id,
    ) -> None:
        """Fetch Canvas course JSON and append path to file_paths; no-op if creds missing."""
        if not (canvas_api_url and canvas_api_key and canvas_course_id):
            return
        try:
            course = CanvasCourse(int(canvas_course_id), canvas_api_url, canvas_api_key)
            canvas_file_path = os.path.join(temp_dir, "canvas_course.json")
            with open(canvas_file_path, "w") as f:
                f.write(course_to_json(course))
            file_paths.append(canvas_file_path)
        except Exception as e:
            logger.warning("Failed to parse Canvas course: %s", e)

    def archive_to_s3(self, file_paths: list, period_id: str) -> list:
        """Upload files to S3 under periods/{period_id}/course materials. Returns keys."""
        keys = []
        for path in file_paths:
            key = upload_file_to_s3(path, folder=f"periods/{period_id}/course materials")
            if key is None:
                logger.warning("S3 upload failed for %s", os.path.basename(path))
                key = f"local/{os.path.basename(path)}"
            keys.append(key)
        return keys

    def ingest_to_openai(self, vector_store_id: str, file_paths: list) -> None:
        """Upload file_paths into an existing vector store, preprocessing large PDFs first."""
        processed = [preprocess_pdf(p) if p.lower().endswith(".pdf") else p for p in file_paths]
        openai_vector_store.upload_files(vector_store_id, processed)

    def run_pipeline(self, period_id: str, user_id: str):
        """Generate and save schedule; log and return None on failure."""
        try:
            result = self._schedule_service.generate_and_save_schedule(period_id, user_id)
            logger.info("Schedule generated for period %s", period_id)
            return result
        except Exception as e:
            logger.warning("Schedule generation failed for %s: %s", period_id, e)
            return None
