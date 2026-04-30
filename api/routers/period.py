import logging
import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.deps import AuthPayload, get_auth
from data_access.teacher_dao import TeacherDAO
from services.period.period_file_helpers import (
    append_canvas_file,
    create_vector_store,
    get_file_presigned_url,
    upload_period_files,
    try_generate_schedule,
)
from services.period.period_management_service import PeriodManagementService
from services.waitlist.WaitlistService import WaitlistService

logger = logging.getLogger(__name__)
router = APIRouter()
period_management_service = PeriodManagementService()
teacher_dao = TeacherDAO()
waitlist_service = WaitlistService()


# ─── Private helpers ──────────────────────────────────────────────────────────

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

@router.get("/periods")
def list_periods(auth: AuthPayload = Depends(get_auth)):
    try:
        result = period_management_service.get_periods_by_owner(auth.sub)
        return {"periods": result}
    except Exception as e:
        logger.error("Unexpected error in list-periods: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/create-period", status_code=201)
def create_period(
    name: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    canvas_api_url: Optional[str] = Form(default=None),
    canvas_api_key: Optional[str] = Form(default=None),
    canvas_course_id: Optional[str] = Form(default=None),
    canvas_course_name: Optional[str] = Form(default=None),
    auth: AuthPayload = Depends(get_auth),
):
    role = auth.role
    if role == "teacher":
        _validate_pilot_access(auth.sub)

    temp_dir = tempfile.mkdtemp()
    try:
        file_paths: List[str] = []
        for upload in files:
            file_path = os.path.join(temp_dir, upload.filename or "")
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(upload.file, dest)
            file_paths.append(file_path)

        if role == "teacher":
            append_canvas_file(temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id)

        vector_store, file_streams = create_vector_store(name, file_paths)

        period = period_management_service.create_period(
            course=name,
            user_id=auth.sub,
            vector_store_id=vector_store.id,
            file_urls=[],
            canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
            canvas_course_name=canvas_course_name,
        )
        period_id = period["period_id"]
        s3_urls = upload_period_files(file_paths, period_id)
        period_management_service.update_file_urls(period_id, [u for u in s3_urls if u])

        for f in file_streams:
            f.close()

        schedule_result = try_generate_schedule(period_id, auth.sub)
        return {"message": "Period created successfully", "period": period, "schedule": schedule_result}

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error in create-period: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/add-files-to-period")
def add_files_to_period(
    period_id: str = Form(...),
    files: List[UploadFile] = File(...),
    auth: AuthPayload = Depends(get_auth),
):
    period = period_management_service.period_dao.get_period_by_id(period_id)
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

        new_file_urls = [u for u in upload_period_files(file_paths, period_id) if u]
        period_management_service.update_file_urls(
            period_id, (period.get("file_urls") or []) + new_file_urls
        )
    except Exception as e:
        logger.error("Error in add-files-to-period: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add files to period")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {"message": f"Successfully added {len(new_file_urls)} files to period", "added_files": new_file_urls}


# ─── Files ────────────────────────────────────────────────────────────────────

@router.get("/get-file/{key:path}")
def get_file_presigned(key: str, auth: AuthPayload = Depends(get_auth)):
    try:
        url = get_file_presigned_url(key)
        return {"url": url}
    except Exception as e:
        logger.error("Error generating presigned URL for %s: %s", key, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve file")
