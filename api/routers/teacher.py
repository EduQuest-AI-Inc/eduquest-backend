import logging
import os
import shutil
import tempfile
from typing import List, Optional

import boto3
from canvasapi import Canvas
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from integrations.canvas_service import Course as CanvasCourse, course_to_json
from services.period.period_schedule_service import PeriodScheduleService
from services.teacher.teacher_service import TeacherService
from services.waitlist.WaitlistService import WaitlistService
from integrations.s3_service import upload_file_to_s3

logger = logging.getLogger(__name__)

from data_access.teacher_dao import TeacherDAO

router = APIRouter()
teacher_service = TeacherService()
period_schedule_service = PeriodScheduleService()
teacher_dao = TeacherDAO()
waitlist_service = WaitlistService()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# Get teacher periods
# ---------------------------------------------------------------------------

@router.get("/periods")
def get_teacher_periods(auth: AuthPayload = Depends(get_auth)):
    try:
        result = teacher_service.get_periods_by_teacher(auth.sub)
        return {"periods": result}
    except Exception as e:
        logger.error("Error in get_teacher_periods: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Create period (multipart)
# ---------------------------------------------------------------------------

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
    user_id = auth.sub

    pilot_waitlist_enabled = os.getenv("PILOT_WAITLIST_ENABLED", "true").lower() == "true"
    if pilot_waitlist_enabled:
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

    temp_dir = tempfile.mkdtemp()
    file_paths: List[str] = []

    try:
        # Save uploaded files to temp dir using sync file handle
        for upload in files:
            file_path = os.path.join(temp_dir, upload.filename)
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(upload.file, dest)
            file_paths.append(file_path)

        # Optionally parse Canvas course into a JSON file
        if canvas_api_url and canvas_api_key and canvas_course_id:
            try:
                canvas_course = CanvasCourse(
                    int(canvas_course_id), canvas_api_url, canvas_api_key
                )
                canvas_json = course_to_json(canvas_course)
                canvas_file_path = os.path.join(temp_dir, "canvas_course.json")
                with open(canvas_file_path, "w") as f:
                    f.write(canvas_json)
                file_paths.append(canvas_file_path)
            except Exception as canvas_error:
                logger.warning("Failed to parse Canvas course: %s", canvas_error)

        # Create OpenAI vector store and upload files
        vector_store = openai_client.vector_stores.create(name=name)
        file_streams = [open(p, "rb") for p in file_paths]
        try:
            if file_streams:
                openai_client.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=vector_store.id,
                    files=file_streams,
                )
        finally:
            for f in file_streams:
                f.close()

        # Create period record (file_urls populated after S3 upload)
        period = teacher_service.create_period(
            course=name,
            user_id=user_id,
            vector_store_id=vector_store.id,
            file_urls=[],
            canvas_course_id=int(canvas_course_id) if canvas_course_id else None,
            canvas_course_name=canvas_course_name,
        )
        period_id = period["period_id"]

        # Upload files to S3 under the actual period_id
        s3_urls: List[str] = []
        for file_path in file_paths:
            url = upload_file_to_s3(
                file_path, folder=f"periods/{period_id}/course materials"
            )
            if url is None:
                url = f"local/{os.path.basename(file_path)}"
            s3_urls.append(url)

        teacher_service.update_period_files(
            period_id, [u for u in s3_urls if u is not None]
        )

        # Auto-generate schedule
        schedule_result = None
        try:
            schedule_result = period_schedule_service.generate_and_save_schedule(
                period_id=period_id, user_id=user_id
            )
        except Exception as schedule_error:
            logger.warning("Failed to auto-generate schedule: %s", schedule_error)

        return {
            "message": "Period created successfully",
            "period": period,
            "schedule": schedule_result,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error in create_period: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Get file from S3
# ---------------------------------------------------------------------------

@router.get("/get-file/{key:path}")
def get_file(key: str, auth: AuthPayload = Depends(get_auth)):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION"),
        )
        bucket = os.getenv("S3_BUCKET_NAME")
        file_obj = s3.get_object(Bucket=bucket, Key=key)
        return StreamingResponse(
            file_obj["Body"],
            media_type=file_obj["ContentType"],
            headers={
                "Content-Disposition": f"inline; filename={key.split('/')[-1]}"
            },
        )
    except Exception as e:
        logger.error("Error retrieving file: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve file")


# ---------------------------------------------------------------------------
# Canvas courses
# ---------------------------------------------------------------------------

class CanvasCoursesRequest(BaseModel):
    api_url: str
    api_key: str


@router.post("/canvas/courses")
def list_canvas_courses(
    body: CanvasCoursesRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        canvas = Canvas(body.api_url, body.api_key)
        current_user = canvas.get_current_user()
        courses = []
        for course in current_user.get_courses(enrollment_type="teacher"):
            try:
                courses.append({
                    "id": course.id,
                    "name": getattr(course, "name", f"Course {course.id}"),
                })
            except Exception:
                continue
        return {"courses": courses}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to Canvas: {e}")


# ---------------------------------------------------------------------------
# Period schedule
# ---------------------------------------------------------------------------

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
            raise HTTPException(
                status_code=404, detail="No schedule found for this period"
            )
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
