import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from routers.deps import AuthPayload, get_auth, get_bot_provider
from bots.protocol import BotProviderProtocol
from services.enrollment.enrollment_service import EnrollmentService
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
    period_service: PeriodService = Depends(_get_period_service),
):
    try:
        EnrollmentService().check_enrolled(auth.sub, body.period_id)
        return period_service.initiate_ltg_conversation(auth.sub, body.period_id)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@router.post("/continue-ltg-conversation")
def continue_ltg_conversation(
    body: ContinueLTGRequest,
    auth: AuthPayload = Depends(get_auth),
    period_service: PeriodService = Depends(_get_period_service),
):
    try:
        return period_service.continue_ltg_conversation(
            auth.sub,
            body.conversation_type,
            body.conversation_id,
            body.message,
            body.period_id,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@router.post("/initiate-homework-agent")
def initiate_homework_agent(
    body: InitiateHomeworkRequest,
    auth: AuthPayload = Depends(get_auth),
    period_service: PeriodService = Depends(_get_period_service),
):
    try:
        user_id = body.user_id or auth.sub
        EnrollmentService().check_enrolled(user_id, body.period_id)
        return period_service.start_homework_agent(user_id, body.period_id)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
