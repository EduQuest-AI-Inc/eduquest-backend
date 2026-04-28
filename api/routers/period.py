import logging
import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from data_access.teacher_dao import TeacherDAO
from services.parent.parent_service import ParentService
from services.period.period_file_helpers import (
    append_canvas_file,
    create_vector_store,
    get_file_presigned_url,
    upload_period_files,
    try_generate_schedule,
)
from services.period.period_management_service import PeriodManagementService
from services.period.period_schedule_service import PeriodScheduleService
from services.period.period_service import PeriodService
from services.waitlist.WaitlistService import WaitlistService

logger = logging.getLogger(__name__)
router = APIRouter()
period_service = PeriodService()
period_management_service = PeriodManagementService()
period_schedule_service = PeriodScheduleService()
parent_service_p = ParentService()
teacher_dao_p = TeacherDAO()
waitlist_service_p = WaitlistService()


class InitiateLTGRequest(BaseModel):
    period_id: str


class ContinueLTGRequest(BaseModel):
    conversation_type: str
    conversation_id: str
    message: str
    period_id: Optional[str] = None


class InitiateHomeworkRequest(BaseModel):
    period_id: str
    user_id: str | None = None


@router.post("/initiate-ltg-conversation")
def initiate_ltg_conversation(
    body: InitiateLTGRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        return period_service.initiate_ltg_conversation(auth.sub, body.period_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/continue-ltg-conversation")
def continue_ltg_conversation(
    body: ContinueLTGRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        return period_service.continue_ltg_conversation(
            auth.sub,
            body.conversation_type,
            body.conversation_id,
            body.message,
            body.period_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initiate-homework-agent")
def initiate_homework_agent(
    body: InitiateHomeworkRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        user_id = body.user_id or auth.sub
        return period_service.start_homework_agent(user_id, body.period_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Owner-facing period list ─────────────────────────────────────────────────

@router.get("/periods")
def list_periods(auth: AuthPayload = Depends(get_auth)):
    try:
        result = period_management_service.get_periods_by_owner(auth.sub)
        return {"periods": result}
    except Exception as e:
        logger.error("Unexpected error in list-periods: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


# ─── Student-facing period routes ─────────────────────────────────────────────

@router.get("/my-periods")
def my_periods(auth: AuthPayload = Depends(get_auth)):
    return period_service.get_my_periods(auth.sub)


class VerifyPeriodRequest(BaseModel):
    period_id: str


@router.post("/verify-period")
def verify_period(body: VerifyPeriodRequest, auth: AuthPayload = Depends(get_auth)):
    period = period_service.verify_period_id(auth.sub, body.period_id)
    return {"message": "Period verified and added to enrollments", "period": period}


class UnenrollRequest(BaseModel):
    period_id: str


@router.post("/unenroll")
def unenroll(body: UnenrollRequest, auth: AuthPayload = Depends(get_auth)):
    return period_service.unenroll_from_period(auth.sub, body.period_id)


# ─── Accept parent invite ──────────────────────────────────────────────────────

class AcceptInviteRequest(BaseModel):
    code: str


@router.post("/accept-parent-invite")
def accept_parent_invite(body: AcceptInviteRequest, auth: AuthPayload = Depends(get_auth)):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Invite code is required")
    try:
        result = parent_service_p.accept_invite(auth.sub, code)
        return result
    except ValueError as ve:
        msg = str(ve)
        if "expired" in msg or "already been used" in msg:
            raise HTTPException(status_code=410, detail=msg)
        if "not found" in msg.lower() or "invalid" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        logger.error("Error in accept-parent-invite: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Period creation (teacher + parent, role-aware) ───────────────────────────

def _validate_pilot_access_p(user_id: str):
    """Raise HTTPException 403 if teacher lacks pilot access."""
    pilot_enabled = os.getenv("PILOT_WAITLIST_ENABLED", "true").lower() == "true"
    if not pilot_enabled:
        return
    teacher = teacher_dao_p.get_teacher_by_id(user_id)
    if not teacher or not teacher.get("pilot_approved", False):
        waitlist_status = waitlist_service_p.get_status(user_id)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Pilot access required to create a class. Please join the pilot waitlist.",
                "code": "PILOT_WAITLIST_REQUIRED",
                "waitlist": waitlist_status,
            },
        )


@router.post("/create-period", status_code=201)
def create_period_unified(
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
        _validate_pilot_access_p(auth.sub)

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


# ─── File access (presigned URL) ──────────────────────────────────────────────

@router.get("/get-file/{key:path}")
def get_file_presigned(key: str, auth: AuthPayload = Depends(get_auth)):
    try:
        url = get_file_presigned_url(key)
        return {"url": url}
    except Exception as e:
        logger.error("Error generating presigned URL for %s: %s", key, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve file")


# ─── Add files to existing period ─────────────────────────────────────────────

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


# ─── Period schedule (teacher + parent) ──────────────────────────────────────

class GenerateScheduleRequest(BaseModel):
    period_id: str


@router.post("/period-schedule/generate")
def generate_period_schedule(
    body: GenerateScheduleRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.generate_and_save_schedule(
            period_id=body.period_id, user_id=auth.sub
        )
        return {"message": "Schedule generated successfully", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error generating period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate schedule")


@router.get("/period-schedule")
def get_period_schedule(
    period_id: str = Query(...),
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.get_schedule(
            period_id=period_id, user_id=auth.sub
        )
        if result is None:
            raise HTTPException(status_code=404, detail="No schedule found for this period")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error getting period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get schedule")


class UpdateScheduleRequest(BaseModel):
    period_id: str
    schedule: dict


@router.put("/period-schedule")
def update_period_schedule(
    body: UpdateScheduleRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.update_schedule(
            period_id=body.period_id,
            user_id=auth.sub,
            schedule_dict=body.schedule,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error updating period schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update schedule")


class SetQuestWeeksRequest(BaseModel):
    period_id: str
    quest_enabled_weeks: List[int]


@router.put("/period-schedule/quest-weeks")
def set_period_quest_weeks(
    body: SetQuestWeeksRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        result = period_schedule_service.set_quest_weeks(
            period_id=body.period_id,
            user_id=auth.sub,
            quest_enabled_weeks=body.quest_enabled_weeks,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Error setting quest weeks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set quest weeks")
