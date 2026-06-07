import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth, get_bot_provider
from bots.protocol import BotProviderProtocol
from services.enrollment.enrollment_service import EnrollmentService
from services.period.period_management_service import PeriodManagementService
from services.period.period_service import PeriodService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_period_service(
    bot_provider: BotProviderProtocol = Depends(get_bot_provider),
) -> PeriodService:
    return PeriodService(bot_provider=bot_provider)


# ─── Request models ───────────────────────────────────────────────────────────

class InitiateLTGRequest(BaseModel):
    period_id: str
    student_id: Optional[str] = None  # set when a class owner runs LTG on behalf of a student


class ContinueLTGRequest(BaseModel):
    conversation_type: str
    conversation_id: str
    message: str
    period_id: Optional[str] = None
    student_id: Optional[str] = None


class InitiateHomeworkRequest(BaseModel):
    period_id: str
    user_id: str | None = None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/initiate-ltg-conversation", response_model=dict[str, Any])
async def initiate_ltg_conversation(
    body: InitiateLTGRequest,
    auth: AuthPayload = Depends(get_auth),
    period_service: PeriodService = Depends(_get_period_service),
):
    if body.student_id and body.student_id != auth.sub:
        period_mgmt = PeriodManagementService(jwt=auth.token)
        period = period_mgmt.get_period_by_id(body.period_id)
        if not period or period.get("owner_id") != auth.sub:
            return JSONResponse(
                status_code=403,
                content={"detail": "Not authorized to run LTG for this student"},
            )
        effective_user_id = body.student_id
    else:
        EnrollmentService(jwt=auth.token).check_enrolled(auth.sub, body.period_id)
        effective_user_id = auth.sub

    return await period_service.initiate_ltg_conversation(effective_user_id, body.period_id)


@router.post("/continue-ltg-conversation", response_model=dict[str, Any])
async def continue_ltg_conversation(
    body: ContinueLTGRequest,
    auth: AuthPayload = Depends(get_auth),
    period_service: PeriodService = Depends(_get_period_service),
):
    if body.student_id and body.student_id != auth.sub:
        if not body.period_id:
            return JSONResponse(status_code=400, content={"detail": "period_id is required when student_id is provided"})
        period_mgmt = PeriodManagementService(jwt=auth.token)
        period = period_mgmt.get_period_by_id(body.period_id)
        if not period or period.get("owner_id") != auth.sub:
            return JSONResponse(
                status_code=403,
                content={"detail": "Not authorized to continue LTG for this student"},
            )
        effective_user_id = body.student_id
    else:
        effective_user_id = auth.sub
    return await period_service.continue_ltg_conversation(
        effective_user_id,
        body.conversation_type,
        body.conversation_id,
        body.message,
        body.period_id,
    )


@router.post("/initiate-homework-agent", response_model=dict[str, Any])
def initiate_homework_agent(
    body: InitiateHomeworkRequest,
    auth: AuthPayload = Depends(get_auth),
    period_service: PeriodService = Depends(_get_period_service),
):
    user_id = body.user_id or auth.sub
    if user_id != auth.sub:
        period_mgmt = PeriodManagementService(jwt=auth.token)
        period = period_mgmt.get_period_by_id(body.period_id)
        if not period or period.get("owner_id") != auth.sub:
            return JSONResponse(
                status_code=403,
                content={"detail": "Not authorized to create quests for this student"},
            )
    EnrollmentService(jwt=auth.token).check_enrolled(user_id, body.period_id)
    return period_service.start_homework_agent(user_id, body.period_id)
