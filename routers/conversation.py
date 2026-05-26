import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Optional, cast

from fastapi import UploadFile

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.deps import AuthPayload, Role, get_auth, get_bot_provider, require_roles
from bots.protocol import BotProviderProtocol
from services.conversation.conversation_service import ConversationService
from services.quest.quest_retrieval_service import QuestRetrievalService
logger = logging.getLogger(__name__)
router = APIRouter()


def _get_conversation_service(
    auth: AuthPayload = Depends(get_auth),
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
) -> ConversationService:
    return ConversationService(bot_provider=bot_provider, jwt=auth.token)


# ---------------------------------------------------------------------------
# Profile assistant
# ---------------------------------------------------------------------------

@router.post("/initiate-profile-assistant", response_model=dict[str, Any])
async def initiate_profile_assistant(
    auth: AuthPayload = Depends(require_roles(Role.STUDENT)),
    svc: ConversationService = Depends(_get_conversation_service),
):
    return await svc.start_profile_assistant(auth.sub)


class ContinueProfileRequest(BaseModel):
    conversation_type: str
    conversation_id: str
    message: str


@router.post("/continue-profile-assistant", response_model=dict[str, Any])
async def continue_profile_assistant(
    body: ContinueProfileRequest,
    auth: AuthPayload = Depends(get_auth),
    svc: ConversationService = Depends(_get_conversation_service),
):
    try:
        return await svc.continue_profile_assistant(
            auth.sub,
            body.conversation_type,
            body.conversation_id,
            body.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Update assistant — dual-mode: multipart (student submission) or JSON (instructor)
# Uses async def so we can await request.form() / request.json(), then dispatches
# the sync service call via run_in_executor to avoid asyncio.run() conflicts.
# ---------------------------------------------------------------------------

@router.post("/initiate-update-assistant", response_model=dict[str, Any])
async def initiate_update_assistant(
    request: Request,
    auth: AuthPayload = Depends(get_auth),
    svc: ConversationService = Depends(_get_conversation_service),
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

            if not individual_quest_id:
                raise HTTPException(
                    status_code=400,
                    detail="individual_quest_id is required for student submissions",
                )
            if not isinstance(individual_quest_id, str):
                raise HTTPException(
                    status_code=400,
                    detail="individual_quest_id must be a string",
                )
            if not week:
                raise HTTPException(
                    status_code=400,
                    detail="week is required for student submissions",
                )

            try:
                quest_retrieval_service = QuestRetrievalService(jwt=auth.token)
                quest_data = quest_retrieval_service.get_quest_by_id(individual_quest_id)
                if not quest_data:
                    raise HTTPException(status_code=404, detail="Quest not found")
                if auth.role == Role.STUDENT and quest_data["user_id"] != auth.sub:
                    raise HTTPException(status_code=403, detail="Not your quest")
                quests_file = json.dumps([quest_data])
            except HTTPException:
                raise
            except Exception:
                raise

            user_id = quest_data["user_id"]
            period_id = quest_data.get("period_id")

            upload_file = cast(UploadFile, upload_file)
            suffix = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ""
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(upload_file.file.read())
            tmp.close()
            temp_path = tmp.name

            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: svc.start_update_assistant(
                        quests_file=quests_file,
                        is_instructor=False,
                        caller_user_id=auth.sub,
                        caller_role=auth.role,
                        week=int(str(week)),
                        submission_file=temp_path,
                        user_id=str(user_id) if user_id else None,
                        period_id=str(period_id) if period_id else None,
                        individual_quest_id=str(individual_quest_id),
                    ),
                )
            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            return result

        else:
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
                lambda: svc.start_update_assistant(
                    quests_file=quests_file,
                    is_instructor=is_instructor,
                    caller_user_id=auth.sub,
                    caller_role=auth.role,
                    week=week,
                    submission_file=submission_file,
                    user_id=user_id,
                    period_id=period_id,
                ),
            )
            return result

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class ContinueUpdateRequest(BaseModel):
    conversation_id: str
    message: str
    user_id: Optional[str] = None


@router.post("/continue-update-assistant", response_model=dict[str, Any])
def continue_update_assistant(
    body: ContinueUpdateRequest,
    auth: AuthPayload = Depends(get_auth),
    svc: ConversationService = Depends(_get_conversation_service),
):
    try:
        return svc.continue_update_assistant(
            user_id=auth.sub,
            caller_role=auth.role,
            conversation_id=body.conversation_id,
            message=body.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
