import asyncio
import logging
import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.deps import AuthPayload, Role, get_auth, require_roles
from data_access.teacher_dao import TeacherDAO
from integrations import openai_vector_store
from integrations.s3_service import download_file_from_s3, generate_presigned_upload_url, get_file_presigned_url
from services.period.period_file_service import PeriodFileService
from services.period.period_management_service import PeriodManagementService
from services.waitlist.waitlist_service import WaitlistService

logger = logging.getLogger(__name__)
router = APIRouter()
period_management_service = PeriodManagementService()
period_file_service = PeriodFileService()
teacher_dao = TeacherDAO()
waitlist_service = WaitlistService()


# ─── Private helpers ──────────────────────────────────────────────────────────

async def _process_period_files(
    period_id: str,
    vector_store_id: str,
    file_paths: list,
    temp_dir: str,
    user_id: str,
    file_keys: list = [],
):
    try:
        # Download presigned-uploaded files from S3 into temp_dir for local processing
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
        archived_keys = period_file_service.archive_to_s3(file_paths, period_id)
        all_s3_keys = [k for k in archived_keys if k] + file_keys
        period_management_service.update_file_urls(period_id, all_s3_keys)

        file_vs_ids = period_file_service.ingest_to_openai(vector_store_id, all_local_paths)
        period_management_service.update_file_vector_store_ids(period_id, file_vs_ids)

        loop = asyncio.get_event_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, period_file_service.run_pipeline, period_id, user_id),
                timeout=300.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Schedule generation timed out for period %s — marking ready anyway", period_id)

        period_management_service.update_processing_status(period_id, "ready")
    except Exception as e:
        logger.error("Background processing failed for period %s: %s", period_id, e, exc_info=True)
        period_management_service.update_processing_status(period_id, "failed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _validate_pilot_access(user_id: str):
    """Raise HTTPException 403 if teacher lacks pilot access."""
    pilot_enabled = os.getenv("PILOT_WAITLIST_ENABLED", "true").lower() == "true"
    if not pilot_enabled:
        return
    teacher = teacher_dao.get_teacher_by_id(user_id)
    if not teacher or not teacher.get("pilot_approved", False):
        waitlist_status = waitlist_service.get_status(user_id)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Pilot access required to create a class. Please join the pilot waitlist.",
                "code": "PILOT_WAITLIST_REQUIRED",
                "waitlist": waitlist_status,
            },
        )


# ─── Period management ────────────────────────────────────────────────────────

class _FileInfo(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"


class _PresignedUploadRequest(BaseModel):
    files: List[_FileInfo]


@router.post("/presigned-upload")
def get_presigned_upload_urls(
    payload: _PresignedUploadRequest,
    auth: AuthPayload = Depends(get_auth),
):
    """Return presigned S3 PUT URLs for direct browser-to-S3 upload."""
    import uuid
    result = []
    for f in payload.files:
        key = f"uploads/{auth.sub}/{uuid.uuid4().hex}/{f.filename}"
        url = generate_presigned_upload_url(key, f.content_type)
        result.append({"filename": f.filename, "key": key, "url": url})
    return {"uploads": result}


@router.get("/periods")
def list_periods(auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT))):
    try:
        result = period_management_service.get_periods_by_owner(auth.sub)
        return {"periods": result}
    except Exception as e:
        logger.error("Unexpected error in list-periods: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/create-period", status_code=201)
def create_period(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    file_keys: List[str] = Form(default=[]),
    canvas_api_url: Optional[str] = Form(default=None),
    canvas_api_key: Optional[str] = Form(default=None),
    canvas_course_id: Optional[str] = Form(default=None),
    canvas_course_name: Optional[str] = Form(default=None),
    start_date: Optional[str] = Form(default=None),
    end_date: Optional[str] = Form(default=None),
    course_description: Optional[str] = Form(default=None),
    auth: AuthPayload = Depends(get_auth),
):
    if auth.role == Role.TEACHER:
        _validate_pilot_access(auth.sub)

    temp_dir = tempfile.mkdtemp()
    try:
        file_paths: List[str] = []
        for upload in files:
            file_path = os.path.join(temp_dir, upload.filename or "")
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(upload.file, dest)
            file_paths.append(file_path)

        if auth.role == Role.TEACHER:
            period_file_service.append_canvas_data(
                temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id
            )

        vector_store_id = openai_vector_store.create_empty(name)

        period = period_management_service.create_period(
            course=name,
            user_id=auth.sub,
            vector_store_id=vector_store_id,
            file_urls=[],
            canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
            canvas_course_name=canvas_course_name,
            start_date=start_date or None,
            end_date=end_date or None,
            course_description=course_description or None,
            processing_status="pending",
        )
        period_id = period["period_id"]

        if auth.role == Role.TEACHER and canvas_api_url and canvas_api_key:
            try:
                teacher_dao.update_canvas_credentials(auth.sub, canvas_api_url, canvas_api_key)
            except Exception as e:
                logger.warning("Failed to persist Canvas credentials for teacher %s: %s", auth.sub, e)

        background_tasks.add_task(
            _process_period_files,
            period_id=period_id,
            vector_store_id=vector_store_id,
            file_paths=file_paths,
            temp_dir=temp_dir,
            user_id=auth.sub,
            file_keys=file_keys,
        )

        return {"message": "Period created", "period": period, "status": "pending"}

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error("Error in create-period: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/add-files-to-period")
def add_files_to_period(
    period_id: str = Form(...),
    files: List[UploadFile] = File(...),
    auth: AuthPayload = Depends(get_auth),
):
    period = period_management_service.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")

    temp_dir = tempfile.mkdtemp()
    try:
        file_paths: List[str] = []
        for upload in files:
            file_path = os.path.join(temp_dir, upload.filename or "")
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(upload.file, dest)
            file_paths.append(file_path)

        new_file_urls = [u for u in period_file_service.archive_to_s3(file_paths, period_id) if u]
        period_management_service.update_file_urls(
            period_id, (period.get("file_urls") or []) + new_file_urls
        )
    except Exception as e:
        logger.error("Error in add-files-to-period: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add files to period")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {"message": f"Successfully added {len(new_file_urls)} files to period", "added_files": new_file_urls}


@router.delete("/period/{period_id}", status_code=204)
def delete_period(
    period_id: str,
    auth: AuthPayload = Depends(require_roles(Role.TEACHER)),
):
    try:
        period_management_service.delete_period(period_id, auth.sub)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Unauthorized")
    except Exception as e:
        logger.error("Error deleting period %s: %s", period_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Files ────────────────────────────────────────────────────────────────────

@router.get("/get-file/{key:path}")
def get_file_presigned(key: str, auth: AuthPayload = Depends(get_auth)):
    try:
        url = get_file_presigned_url(key)
        return {"url": url}
    except Exception as e:
        logger.error("Error generating presigned URL for %s: %s", key, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve file")
