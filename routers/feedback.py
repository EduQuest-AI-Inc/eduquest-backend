from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from routers.deps import AuthPayload, get_auth
from responses.feedback import FeedbackResponse
from services.feedback.feedback_service import FeedbackService

router = APIRouter()
_svc = FeedbackService()


class FeedbackRequest(BaseModel):
    message: str
    page: Optional[str] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message cannot be empty")
        if len(stripped) > 1000:
            raise ValueError("message must be 1000 characters or fewer")
        return stripped


@router.post("/submit", response_model=FeedbackResponse)
def submit_feedback(
    body: FeedbackRequest,
    auth: AuthPayload = Depends(get_auth),
) -> dict:
    _svc.submit(auth.sub, body.message, page=body.page)
    return {"success": True}
