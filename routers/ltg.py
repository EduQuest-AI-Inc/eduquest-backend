import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth
from services.enrollment.enrollment_service import EnrollmentService
from services.period.period_service import PeriodService

logger = logging.getLogger(__name__)
router = APIRouter()
period_service = PeriodService()


# ─── Request models ───────────────────────────────────────────────────────────

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


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/initiate-ltg-conversation")
def initiate_ltg_conversation(
    body: InitiateLTGRequest,
    auth: AuthPayload = Depends(get_auth),
):
    EnrollmentService().check_enrolled(auth.sub, body.period_id)
    return period_service.initiate_ltg_conversation(auth.sub, body.period_id)


@router.post("/continue-ltg-conversation")
def continue_ltg_conversation(
    body: ContinueLTGRequest,
    auth: AuthPayload = Depends(get_auth),
):
    return period_service.continue_ltg_conversation(
        auth.sub,
        body.conversation_type,
        body.conversation_id,
        body.message,
        body.period_id,
    )


@router.post("/initiate-homework-agent")
def initiate_homework_agent(
    body: InitiateHomeworkRequest,
    auth: AuthPayload = Depends(get_auth),
):
    user_id = body.user_id or auth.sub
    return period_service.start_homework_agent(user_id, body.period_id)
