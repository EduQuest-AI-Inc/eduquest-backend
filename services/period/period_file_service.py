import logging
import os

from integrations.canvas_service import Course as CanvasCourse, course_to_json
from integrations.s3_service import upload_file_to_s3
from integrations import openai_vector_store
from utils.pdf_utils import preprocess_pdf

logger = logging.getLogger(__name__)


class PeriodFileService:
    def __init__(self, material_files_dao=None) -> None:
        from data_access.material_files_dao import MaterialFilesDAO
        self._material_files_dao = material_files_dao or MaterialFilesDAO()

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

    def ingest_to_openai(self, period_vector_store_id: str, file_paths: list) -> list:
        """Ingest files into vector stores with deduplication by SHA-256 hash.

        JSON files (Canvas data) go to the per-period VS. All other files get their own
        shared vector store — if a file was previously uploaded by any period, its existing
        VS is reused with no re-upload and no re-embedding.

        Returns list of file-level vector store IDs."""
        import hashlib
        import json

        dao = self._material_files_dao
        file_vs_ids = []

        for original_path in file_paths:
            if original_path.lower().endswith(".json"):
                with open(original_path) as f:
                    openai_vector_store.upload_json(period_vector_store_id, json.load(f))
                continue

            with open(original_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            existing = dao.get_by_hash(file_hash)
            if existing:
                logger.warning("Dedup hit for %s — reusing VS %s", os.path.basename(original_path), existing["vector_store_id"])
                file_vs_ids.append(existing["vector_store_id"])
                continue

            processed_path = preprocess_pdf(original_path) if original_path.lower().endswith(".pdf") else original_path
            vs_id, file_id = openai_vector_store.create_file_store(
                processed_path, name=os.path.basename(original_path)
            )
            dao.insert(file_hash, file_id, vs_id)
            file_vs_ids.append(vs_id)

        return file_vs_ids

