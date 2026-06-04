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

from routers.deps import AuthPayload, Role, get_auth, get_bot_provider, get_period as _get_period_dep, get_period_file_service, require_active_membership, require_roles
from responses.period import (
    AddFilesResponse,
    ArchivePeriodResponse,
    CreatePeriodResponse,
    ForkMetadataResponse,
    GetPeriodResponse,
    MultipartCompleteResponse,
    MultipartInitResponse,
    PeriodListResponse,
    PresignedFileResponse,
    SummerQuestGenerateResponse,
    UnarchivePeriodResponse,
    UpdatePeriodResponse,
)
from bots.protocol import BotProviderProtocol
from integrations.s3_service import (
    complete_multipart_upload,
    create_multipart_upload,
    generate_presigned_part_url,
    get_file_presigned_url,
)
from services.billing.membership_service import (
    MembershipRequiredError,
    MembershipService,
    PlanLimitExceededError,
)
from services.parent.parent_service import ParentService
from services.period.period_summer_quest_service import PeriodSummerQuestService
from models.period import CourseMetadata
from services.period.period_management_service import PeriodManagementService
from services.user.teacher_service import TeacherService

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.post("/multipart-init", response_model=MultipartInitResponse)
def multipart_init(payload: _MultipartInitRequest, auth: AuthPayload = Depends(get_auth)):
    """Create a multipart upload and return presigned PUT URLs for all parts."""
    safe_name = _safe_filename(payload.filename)
    key = f"uploads/{auth.sub}/{uuid.uuid4().hex}/{safe_name}"
    upload_id = create_multipart_upload(key, payload.content_type)
    total_parts = max(1, math.ceil(payload.file_size / _PART_SIZE))
    part_urls = [generate_presigned_part_url(key, upload_id, i + 1) for i in range(total_parts)]
    return {"key": key, "upload_id": upload_id, "part_urls": part_urls}


@router.post("/multipart-complete", response_model=MultipartCompleteResponse)
def multipart_complete(payload: _MultipartCompleteRequest, auth: AuthPayload = Depends(get_auth)):
    parts = [{"PartNumber": p.part_number, "ETag": p.etag} for p in payload.parts]
    key = complete_multipart_upload(payload.key, payload.upload_id, parts)
    return {"key": key}


@router.get("/periods", response_model=PeriodListResponse)
def list_periods(auth: AuthPayload = Depends(require_roles(Role.TEACHER, Role.PARENT))):
    # Listing is allowed regardless of membership so paying users can see their
    # classes and lapsed users still see what they have but cannot manage them.
    svc = PeriodManagementService(jwt=auth.token)
    result = svc.get_periods_by_owner(auth.sub)
    return {"periods": result}


@router.post("/create-period", status_code=201, response_model=CreatePeriodResponse)
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
    grade_level: Optional[str] = Form(default=None),
    mastery_threshold: Optional[float] = Form(default=None),
    learning_objectives: Optional[str] = Form(default=None),
    primary_standard: Optional[str] = Form(default=None),
    additional_standards: List[str] = Form(default=[]),
    specific_standard_codes: Optional[str] = Form(default=None),
    status: Optional[str] = Form(default="pending"),
    is_summer_quest: bool = Form(default=False),
    student_id: Optional[str] = Form(default=None),
    auth: AuthPayload = Depends(get_auth),
    period_file_svc=Depends(get_period_file_service),
):
    if status not in ("pending", "setup_draft"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    if student_id:
        if auth.role != Role.PARENT:
            raise HTTPException(status_code=400, detail="Only parents can specify student_id")
        linked = ParentService().get_linked_student_ids(auth.sub)
        if student_id not in linked:
            raise HTTPException(status_code=403, detail="student_id is not a linked child")
        effective_owner_id = student_id
    else:
        effective_owner_id = auth.sub

    # Summer side quests are free — no membership check required.
    if not is_summer_quest:
        try:
            MembershipService(jwt=auth.token).check_can_create_class(auth.sub, auth.role.value)
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
        period_mgmt = PeriodManagementService(jwt=auth.token)
        period = period_mgmt.create_period(
            course=name,
            user_id=effective_owner_id,
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
            is_summer_quest=is_summer_quest,
        )
        period_id = period["period_id"]

        if auth.role == Role.TEACHER and canvas_api_url and canvas_api_key:
            try:
                TeacherService(jwt=auth.token).update_canvas_credentials(auth.sub, canvas_api_url, canvas_api_key)
            except Exception as e:
                logger.warning("Failed to persist Canvas credentials for teacher %s: %s", auth.sub, e)

        if is_draft:
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            background_tasks.add_task(
                period_file_svc.process_background,
                period_id=period_id,
                owner_id=effective_owner_id,
                course_name=name,
                file_paths=file_paths,
                temp_dir=temp_dir,
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


@router.patch("/{period_id}/setup", response_model=UpdatePeriodResponse)
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
    period_file_svc=Depends(get_period_file_service),
):
    if status not in ("pending", "setup_draft"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    period_mgmt = PeriodManagementService(jwt=auth.token)
    period = period_mgmt.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if period.get("forked_from_period_id"):
        raise HTTPException(status_code=403, detail="Use /period/{period_id}/fork-metadata to update a forked class")
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

        updated = period_mgmt.update_setup(period_id, updates)

        if auth.role == Role.TEACHER and canvas_api_url and canvas_api_key:
            try:
                TeacherService(jwt=auth.token).update_canvas_credentials(auth.sub, canvas_api_url, canvas_api_key)
            except Exception as e:
                logger.warning("Failed to persist Canvas credentials for teacher %s: %s", auth.sub, e)

        if is_finalizing:
            background_tasks.add_task(
                period_file_svc.process_background,
                period_id=period_id,
                owner_id=period["owner_id"],
                course_name=name or period.get("name", ""),
                file_paths=file_paths,
                temp_dir=temp_dir,
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


@router.post("/add-files-to-period", response_model=AddFilesResponse)
def add_files_to_period(
    payload: _AddFilesRequest,
    auth: AuthPayload = Depends(require_active_membership),
):
    period_mgmt = PeriodManagementService(jwt=auth.token)
    period = period_mgmt.get_period_by_id(payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if period.get("forked_from_period_id"):
        raise HTTPException(status_code=403, detail="Cannot add files to a forked class")

    existing = period.get("file_urls") or []
    period_mgmt.update_file_urls(payload.period_id, existing + payload.file_keys)
    return {"message": f"Successfully added {len(payload.file_keys)} files to period", "added_files": payload.file_keys}


@router.get("/{period_id}", response_model=GetPeriodResponse)
def get_period(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
    period: dict = Depends(_get_period_dep),
):
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return {"period": period}


@router.delete("/{period_id}", status_code=204, response_model=None)
def delete_period(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
    period: dict = Depends(_get_period_dep),
):
    try:
        PeriodManagementService(jwt=auth.token).delete_period(period_id, auth.sub, period=period)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Unauthorized")


@router.patch("/{period_id}/archive", response_model=ArchivePeriodResponse)
def archive_period(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
    period: dict = Depends(_get_period_dep),
):
    updated = PeriodManagementService(jwt=auth.token).archive_period(
        period_id, auth.sub, period=period
    )
    return {"message": "Period archived", "period": updated}


@router.patch("/{period_id}/unarchive", response_model=UnarchivePeriodResponse)
def unarchive_period(
    period_id: str,
    auth: AuthPayload = Depends(require_active_membership),
    period: dict = Depends(_get_period_dep),
):
    updated = PeriodManagementService(jwt=auth.token).unarchive_period(
        period_id, auth.sub, period=period
    )
    return {"message": "Period unarchived", "period": updated}


# ─── Fork metadata ────────────────────────────────────────────────────────────

class _ForkMetadataUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    grade_level: Optional[str] = None
    mastery_threshold: Optional[float] = None


@router.patch("/{period_id}/fork-metadata", response_model=ForkMetadataResponse)
def update_fork_metadata(
    period_id: str,
    body: _ForkMetadataUpdate,
    auth: AuthPayload = Depends(require_active_membership),
):
    period_mgmt = PeriodManagementService(jwt=auth.token)
    period = period_mgmt.get_period_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.get("owner_id") != auth.sub:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if not period.get("forked_from_period_id"):
        raise HTTPException(
            status_code=400,
            detail="Use /period/{period_id}/setup to update a non-forked class",
        )
    _ALLOWED = {"name", "start_date", "end_date", "grade_level", "mastery_threshold"}
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _ALLOWED}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    updated = period_mgmt.update_setup(period_id, updates)
    return {"message": "Fork settings updated", "period": updated}


# ─── Summer side quests ───────────────────────────────────────────────────────


@router.post("/{period_id}/summer-quests/generate", status_code=202, response_model=SummerQuestGenerateResponse)
def generate_summer_quests(
    period_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthPayload = Depends(get_auth),
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
    period: dict = Depends(_get_period_dep),
):
    if period.get("owner_id") != auth.sub:
        if auth.role == Role.PARENT:
            linked = ParentService().get_linked_student_ids(auth.sub)
            if period.get("owner_id") not in linked:
                raise HTTPException(status_code=403, detail="Unauthorized")
        else:
            raise HTTPException(status_code=403, detail="Unauthorized")
    if not period.get("is_summer_quest"):
        raise HTTPException(status_code=400, detail="This endpoint is only for summer side quests")

    svc = PeriodSummerQuestService(bot_provider=bot_provider)
    background_tasks.add_task(svc.run_as_background_task, owner_id=period["owner_id"], period_id=period_id)
    return {"message": "Summer quest generation started"}


# ─── Files ────────────────────────────────────────────────────────────────────

@router.get("/get-file/{key:path}", response_model=PresignedFileResponse)
def get_file_presigned(key: str, auth: AuthPayload = Depends(get_auth)):
    url = get_file_presigned_url(key)
    return {"url": url}
