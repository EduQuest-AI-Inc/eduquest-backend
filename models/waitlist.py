from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
import uuid


def _generate_referral_code() -> str:
    return uuid.uuid4().hex[:8].upper()


class WaitlistEntry(BaseModel):
    waitlist_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    email: str
    joined_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    position: int = 0
    referral_code: str = Field(default_factory=_generate_referral_code)
    referred_by: Optional[str] = None
    status: str = "pending"

    def to_item(self):
        return self.model_dump()
