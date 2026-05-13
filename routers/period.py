import logging
import math
import os
import re
import shutil
import tempfile
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_auth, get_bot_provider, require_active_membership, require_roles
from bots.protocol import BotProviderProtocol
from integrations import openai_vector_store
from integrations.s3_service import (
    complete_multipart_upload,
    create_multipart_upload,
    download_file_from_s3,
    generate_presigned_part_url,
    get_file_presigned_url,
)
from services.billing.membership_service import (
    MembershipRequiredError,
    MembershipService,
    PlanLimitExceededError,
)
from services.period.period_file_service import PeriodFileService
from models.period import CourseMetadata
from services.curriculum.curriculum_service import CurriculumService
from services.period.period_management_service import PeriodManagementService
from services.user.teacher_service import TeacherService

logger = logging.getLogger(__name__)
router = APIRouter()
period_management_service = PeriodManagementService()
period_file_service = PeriodFileService()
_teacher_service = TeacherService()
membership_service = MembershipService()


# ─── Private helpers ──────────────────────────────────────────────────────────

def _process_period_files(
    period_id: str,
    course_name: str,
    file_paths: list,
    temp_dir: str,
    user_id: str,
    bot_provider: BotProviderProtocol,
    file_keys: list = [],
    canvas_api_url: str | None = None,
    canvas_api_key: str | None = None,
    canvas_course_id: str | None = None,
):
    try:
        period_file_service.append_canvas_data(
            temp_dir, file_paths, canvas_api_url, canvas_api_key, canvas_course_id
        )

        vector_store_id = openai_vector_store.create_empty(course_name)
        period_management_service.update_vector_store_id(period_id, vector_store_id)

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

        try:
            file_vs_ids = period_file_service.ingest_to_openai(vector_store_id, all_local_paths)
        except Exception as e:
            logger.error("ingest_to_openai failed for period %s: %s", period_id, e, exc_info=True)
            raise
        period_management_service.update_file_vector_store_ids(period_id, file_vs_ids)

        period_management_service.update_processing_status(period_id, "ready")

        try:
            CurriculumService(bot_provider=bot_provider)._run_generation(period_id)
        except Exception as exc:
            logger.error("Auto curriculum generation failed for period %s: %s", period_id, exc, exc_info=True)
    except Exception as e:
        logger.error("Background processing failed for period %s: %s", period_id, e, exc_info=True)
        period_management_service.update_processing_status(period_id, "failed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _membership_required_response(err: MembershipRequiredError) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "error": "Active membership required",
            "code": "MEMBERSHIP_REQUIRED",
            "status": err.access.status.value,
            "trial_ends_at": err.access.trial_ends_at,
        },
    )


# ─── Period management ────────────────────────────────────────────────────────

_PART_SIZE = 10 * 1024 * 1024  # 10 MB


class _MultipartInitRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    file_size: int


class _PartInfo(BaseModel):
    part_number: int
    etag: str


class _MultipartCompleteRequest(BaseModel):
    key: str
    upload_id: str
    parts: List[_PartInfo]


def _safe_filename(filename: str) -> str:
    name = os.path.basename(filename)
    return re.sub(r"[^\w.\-]", "_", name) or "upload"


@router.post("/multipart-init")
def multipart_init(payload: _MultipartInitRequest, auth: AuthPayload = Depends(get_auth)):
    """Create a multipart upload and return presigned PUT URLs for all parts."""
    safe_name = _safe_filename(payload.filename)
    key = f"uploads/{auth.sub}/{uuid.uuid4().hex}/{safe_name}"
    upload_id = create_multipart_upload(key, payload.content_type)
    total_parts = max(1, math.ceil(payload.file_size / _PART_SIZE))
    part_urls = [generate_presigned_part_url(key, upload_id, i + 1) for i in range(total_parts)]
    return {"key": key, "upload_id": upload_id, "part_urls": part_urls}


@router.post("/multipart-complete")
def multipart_complete(payload: _MultipartCompleteRequest, auth: AuthPayload = Depends(get_auth)):
    parts = [{"PartNumber": p.part_number, "ETag": p.etag} for p in payload.parts]
    key = complete_multipart_upload(payload.key, payload.upload_id, parts)
    return {"key": key}


@router.get("/periods")
def list_periods(auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT))):
    # Listing is allowed regardless of membership so paying users can see their
    # classes and lapsed users still see what they have but cannot manage them.
    result = period_management_service.get_periods_by_owner(auth.sub)
    return {"periods": result}


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
    start_date: str = Form(...),
    end_date: str = Form(...),
    course_description: str = Form(...),
    grade_level: str = Form(...),
    mastery_threshold: Optional[float] = Form(default=None),
    learning_objectives: Optional[str] = Form(default=None),
    primary_standard: Optional[str] = Form(default=None),
    additional_standards: List[str] = Form(default=[]),
    specific_standard_codes: Optional[str] = Form(default=None),
    status: Optional[str] = Form(default="pending"),
    auth: AuthPayload = Depends(get_auth),
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
):
    if status not in ("pending", "setup_draft"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    # Membership gate: parent/teacher need an active trial or paid subscription
    # to create classes, and the plan's class limit is enforced server-side.
    try:
        membership_service.check_can_create_class(auth.sub, auth.role.value)
    except MembershipRequiredError as e:
        raise _membership_required_response(e)
    except PlanLimitExceededError as e:
        raise HTTPException(
            status_code=403,
            detail={"error": str(e), "code": "PLAN_LIMIT_EXCEEDED"},
        )

    raw_metadata = CourseMetadata(
        learning_objectives=learning_objectives,
        primary_standard=primary_standard,
        additional_standards=additional_standards or [],
        specific_standard_codes=specific_standard_codes,
    )
    course_metadata = raw_metadata if raw_metadata.model_dump(exclude_none=True) else None

    temp_dir = tempfile.mkdtemp()
    try:
        file_paths: List[str] = []
        for upload in files:
            file_path = os.path.join(temp_dir, upload.filename or "")
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(upload.file, dest)
            file_paths.append(file_path)

        is_draft = status == "setup_draft"
        period = period_management_service.create_period(
            course=name,
            user_id=auth.sub,
            vector_store_id="",
            file_urls=file_keys if is_draft else [],
            canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
            canvas_course_name=canvas_course_name,
            start_date=start_date,
            end_date=end_date,
            grade_level=grade_level,
            mastery_threshold=mastery_threshold,
            course_description=course_description,
            course_metadata=course_metadata,
            processing_status="ready" if is_draft else "pending",
            status=status,
        )
        period_id = period["period_id"]

        if auth.role == Role.TEACHER and canvas_api_url and canvas_api_key:
            try:
                _teacher_service.update_canvas_credentials(auth.sub, canvas_api_url, canvas_api_key)
            except Exception as e:
                logger.warning("Failed to persist Canvas credentials for teacher %s: %s", auth.sub, e)

        if is_draft:
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            background_tasks.add_task(
                _process_period_files,
                period_id=period_id,
                course_name=name,
                file_paths=file_paths,
                temp_dir=temp_dir,
                user_id=auth.sub,
                bot_provider=bot_provider,
                file_keys=file_keys,
                canvas_api_url=canvas_api_url if auth.role == Role.TEACHER else None,
                canvas_api_key=canvas_api_key if auth.role == Role.TEACHER else None,
                canvas_course_id=canvas_course_id if auth.role == Role.TEACHER else None,
            )

        return {"message": "Period created", "period": period, "status": status}

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@router.patch("/period/{period_id}/setup")
def update_period_setup(
    period_id: str,
    background_tasks: BackgroundTasks,
    name: Optional[str] = Form(default=None),
    files: List[UploadFile] = File(default=[]),
    file_keys: List[str] = Form(default=[]),
    canvas_api_url: Optional[str] = Form(default=None),
    canvas_api_key: Optional[str] = Form(default=None),
    canvas_course_id: Optional[str] = Form(default=None),
    canvas_course_name: Optional[str] = Form(default=None),
    start_date: Optional[str] = Form(default=None),
    end_date: Optional[str] = Form(default=None),
    course_description: Optional[str] = Form(default=None),
    grade_level: Optional[str] = Form(default=None),
    mastery_threshold: Optional[float] = Form(default=None),
    learning_objectives: Optional[str] = Form(default=None),
    primary_standard: Optional[str] = Form(default=None),
    additional_standards: List[str] = Form(default=[]),
    specific_standard_codes: Optional[str] = Form(default=None),
    status: Optional[str] = Form(default="setup_draft"),
    auth: AuthPayload = Depends(require_active_membership),
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
):
    if status not in ("pending", "setup_draft"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    period = period_management_service.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if period.get("status") != "setup_draft":
        raise HTTPException(status_code=400, detail="Period is not a setup draft")

    raw_metadata = CourseMetadata(
        learning_objectives=learning_objectives,
        primary_standard=primary_standard,
        additional_standards=additional_standards or [],
        specific_standard_codes=specific_standard_codes,
    )
    course_metadata = raw_metadata if raw_metadata.model_dump(exclude_none=True) else None

    existing_file_keys = period.get("file_urls") or []
    all_file_keys = existing_file_keys + file_keys
    is_finalizing = status == "pending"

    updates: dict = {
        "status": status,
        "file_urls": [] if is_finalizing else all_file_keys,
        "processing_status": "pending" if is_finalizing else "ready",
    }
    if name is not None:
        updates["name"] = name
    if course_description is not None:
        updates["course_description"] = course_description or None
    if start_date is not None:
        updates["start_date"] = start_date or None
    if end_date is not None:
        updates["end_date"] = end_date or None
    if grade_level is not None:
        updates["grade_level"] = grade_level or None
    if mastery_threshold is not None:
        updates["mastery_threshold"] = mastery_threshold
    if canvas_course_id is not None:
        updates["canvas_course_id"] = int(canvas_course_id) if canvas_course_id else None
    if canvas_course_name is not None:
        updates["canvas_course_name"] = canvas_course_name or None
    if course_metadata:
        updates["course_metadata"] = course_metadata.model_dump()

    temp_dir = tempfile.mkdtemp()
    try:
        file_paths: List[str] = []
        for upload in files:
            file_path = os.path.join(temp_dir, upload.filename or "")
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(upload.file, dest)
            file_paths.append(file_path)

        updated = period_management_service.update_setup(period_id, updates)

        if auth.role == Role.TEACHER and canvas_api_url and canvas_api_key:
            try:
                _teacher_service.update_canvas_credentials(auth.sub, canvas_api_url, canvas_api_key)
            except Exception as e:
                logger.warning("Failed to persist Canvas credentials for teacher %s: %s", auth.sub, e)

        if is_finalizing:
            background_tasks.add_task(
                _process_period_files,
                period_id=period_id,
                course_name=name or period.get("name", ""),
                file_paths=file_paths,
                temp_dir=temp_dir,
                user_id=auth.sub,
                bot_provider=bot_provider,
                file_keys=all_file_keys,
                canvas_api_url=canvas_api_url if auth.role == Role.TEACHER else None,
                canvas_api_key=canvas_api_key if auth.role == Role.TEACHER else None,
                canvas_course_id=canvas_course_id if auth.role == Role.TEACHER else None,
            )
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return {"message": "Period updated", "period": updated, "status": status}

    except HTTPException:
        raise
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class _AddFilesRequest(BaseModel):
    period_id: str
    file_keys: List[str]


@router.post("/add-files-to-period")
def add_files_to_period(
    payload: _AddFilesRequest,
    auth: AuthPayload = Depends(require_active_membership),
):
    period = period_management_service.get_period_by_id(payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")

    existing = period.get("file_urls") or []
    period_management_service.update_file_urls(payload.period_id, existing + payload.file_keys)
    return {"message": f"Successfully added {len(payload.file_keys)} files to period", "added_files": payload.file_keys}


@router.get("/period/{period_id}")
def get_period(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    period = period_management_service.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return {"period": period}


@router.delete("/period/{period_id}", status_code=204)
def delete_period(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
):
    try:
        period_management_service.delete_period(period_id, auth.sub)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Unauthorized")


# ─── Files ────────────────────────────────────────────────────────────────────

@router.get("/get-file/{key:path}")
def get_file_presigned(key: str, auth: AuthPayload = Depends(get_auth)):
    url = get_file_presigned_url(key)
    return {"url": url}
