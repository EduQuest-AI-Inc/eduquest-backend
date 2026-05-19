import logging
import os
import shutil
from typing import TYPE_CHECKING, Optional

from integrations.canvas_service import Course as CanvasCourse, course_to_json
from integrations.s3_service import upload_file_to_s3, download_file_from_s3
from integrations import openai_vector_store
from utils.pdf_utils import preprocess_pdf

if TYPE_CHECKING:
    from bots.protocol import BotProviderProtocol
    from services.period.period_management_service import PeriodManagementService
    from services.curriculum.curriculum_service import CurriculumService

logger = logging.getLogger(__name__)


class PeriodFileService:
    def __init__(
        self,
        material_files_dao=None,
        bot_provider: Optional["BotProviderProtocol"] = None,
        period_management_service: Optional["PeriodManagementService"] = None,
        curriculum_service: Optional["CurriculumService"] = None,
    ) -> None:
        from data_access.material_files_dao import MaterialFilesDAO
        self._material_files_dao = material_files_dao or MaterialFilesDAO()
        self._bot_provider: Optional["BotProviderProtocol"] = bot_provider
        self._period_mgmt: Optional["PeriodManagementService"] = period_management_service
        self._curriculum_svc: Optional["CurriculumService"] = curriculum_service

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

    def process_background(
        self,
        period_id: str,
        course_name: str,
        file_paths: list,
        temp_dir: str,
        file_keys: list | None = None,
        canvas_api_url: str | None = None,
        canvas_api_key: str | None = None,
        canvas_course_id: str | None = None,
    ) -> None:
        """Background task: ingest files, create vector store, trigger curriculum generation."""
        assert self._bot_provider is not None, "bot_provider is required for process_background"
        assert self._period_mgmt is not None, "period_management_service is required for process_background"
        assert self._curriculum_svc is not None, "curriculum_service is required for process_background"
        file_keys = file_keys or []
        try:
            self.append_canvas_data(
                temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id
            )

            vector_store_id = self._bot_provider.create_vector_store(course_name)
            self._period_mgmt.update_vector_store_id(period_id, vector_store_id)

            s3_local_paths = []
            for key in file_keys:
                filename = key.split("/")[-1]
                dest = os.path.join(temp_dir, filename)
                if download_file_from_s3(key, dest):
                    s3_local_paths.append(dest)
                else:
                    logger.warning("Skipping key %s — S3 download failed", key)

            all_local_paths = file_paths + s3_local_paths

            # Archive only server-generated files (e.g. Canvas JSON); presigned files already in S3
            archived_keys = self.archive_to_s3(file_paths, period_id)
            all_s3_keys = [k for k in archived_keys if k] + file_keys
            self._period_mgmt.update_file_urls(period_id, all_s3_keys)

            try:
                file_vs_ids = self._bot_provider.ingest_files_to_vector_store(vector_store_id, all_local_paths)
            except Exception as exc:
                logger.error("ingest_files_to_vector_store failed for period %s: %s", period_id, exc, exc_info=True)
                raise
            self._period_mgmt.update_file_vector_store_ids(period_id, file_vs_ids)

            self._period_mgmt.update_processing_status(period_id, "ready")

            try:
                current_period = self._period_mgmt.get_period_by_id(period_id)
                if current_period and current_period.get("status") not in {"generating", "draft", "approved"}:
                    self._curriculum_svc.run_generation(period_id)
                else:
                    logger.info(
                        "Auto curriculum generation skipped for period %s: status=%s",
                        period_id, (current_period or {}).get("status"),
                    )
            except Exception as exc:
                logger.error("Auto curriculum generation failed for period %s: %s", period_id, exc, exc_info=True)
        except Exception as exc:
            logger.error("Background processing failed for period %s: %s", period_id, exc, exc_info=True)
            self._period_mgmt.update_processing_status(period_id, "failed")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
