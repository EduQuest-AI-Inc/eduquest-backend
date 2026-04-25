from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from constants.timeouts import INVITE_EXPIRY_HOURS


def default_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)).isoformat()


class ParentInvite(BaseModel):
    code: str
    user_id: str
    expires_at: str = Field(default_factory=default_expiry)
    used: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
