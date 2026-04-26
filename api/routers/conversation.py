import asyncio
import json
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.deps import AuthPayload, get_auth
from services.conversation.conversation_service import ConversationService
from utils.conversion_utils import convert_decimals as _convert_decimals

router = APIRouter()
conversation_service = ConversationService()


# ---------------------------------------------------------------------------
# Profile assistant
# ---------------------------------------------------------------------------

@router.post("/initiate-profile-assistant")
def initiate_profile_assistant(auth: AuthPayload = Depends(get_auth)):
    try:
        return conversation_service.start_profile_assistant(auth.token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ContinueProfileRequest(BaseModel):
    conversation_type: str
    conversation_id: str
    message: str


@router.post("/continue-profile-assistant")
def continue_profile_assistant(
    body: ContinueProfileRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        return conversation_service.continue_profile_assistant(
            auth.token,
            body.conversation_type,
            body.conversation_id,
            body.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Update assistant — dual-mode: multipart (student submission) or JSON (instructor)
# Uses async def so we can await request.form() / request.json(), then dispatches
# the sync service call via run_in_executor to avoid asyncio.run() conflicts.
# ---------------------------------------------------------------------------

@router.post("/initiate-update-assistant")
async def initiate_update_assistant(
    request: Request,
    auth: AuthPayload = Depends(get_auth),
):
    loop = asyncio.get_running_loop()
    content_type = request.headers.get("content-type", "")

    try:
        if "multipart" in content_type:
            form = await request.form()
            upload_file = form.get("file")
            if not upload_file:
                raise HTTPException(status_code=400, detail="No file provided")

            individual_quest_id = form.get("individual_quest_id")
            week = form.get("week")
            user_id = form.get("user_id")
            period_id = form.get("period_id")

            if not individual_quest_id:
                raise HTTPException(
                    status_code=400,
                    detail="individual_quest_id is required for student submissions",
                )
            if not week:
                raise HTTPException(
                    status_code=400,
                    detail="week is required for student submissions",
                )

            # Fetch quest data to build quests_file JSON
            try:
                from data_access.individual_quest_dao import IndividualQuestDAO
                quest_data = IndividualQuestDAO().get_individual_quest_by_id(individual_quest_id)
                if not quest_data:
                    raise HTTPException(status_code=404, detail="Quest not found")
                quest_data = _convert_decimals(quest_data)
                quests_file = json.dumps([quest_data])
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to fetch quest: {e}")

            # Save uploaded file to a temp path synchronously via SpooledTemporaryFile
            suffix = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ""
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(upload_file.file.read())
            tmp.close()
            temp_path = tmp.name

            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: conversation_service.start_update_assistant(
                        auth_token=auth.token,
                        quests_file=quests_file,
                        is_instructor=False,
                        week=int(week),
                        submission_file=temp_path,
                        user_id=user_id,
                        period_id=period_id,
                        individual_quest_id=individual_quest_id,
                    ),
                )
            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            return result

        else:
            # JSON path
            data = await request.json()
            quests_file = data.get("quests_file")
            is_instructor = data.get("is_instructor", False)
            week = data.get("week")
            submission_file = data.get("submission_file")
            user_id = data.get("user_id")
            period_id = data.get("period_id")

            if not quests_file:
                raise HTTPException(status_code=400, detail="quests_file is required")
            if not is_instructor:
                if not week:
                    raise HTTPException(
                        status_code=400,
                        detail="week is required for student submissions",
                    )
                if not submission_file:
                    raise HTTPException(
                        status_code=400,
                        detail="submission_file is required for student submissions",
                    )

            result = await loop.run_in_executor(
                None,
                lambda: conversation_service.start_update_assistant(
                    auth_token=auth.token,
                    quests_file=quests_file,
                    is_instructor=is_instructor,
                    week=week,
                    submission_file=submission_file,
                    user_id=user_id,
                    period_id=period_id,
                ),
            )
            return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ContinueUpdateRequest(BaseModel):
    conversation_id: str
    message: str
    user_id: Optional[str] = None


@router.post("/continue-update-assistant")
def continue_update_assistant(
    body: ContinueUpdateRequest,
    auth: AuthPayload = Depends(get_auth),
):
    try:
        return conversation_service.continue_update_assistant(
            auth_token=auth.token,
            conversation_id=body.conversation_id,
            message=body.message,
            user_id=body.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
