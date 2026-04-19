from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from constants.timeouts import INVITE_EXPIRY_HOURS


def default_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)).isoformat()


class ParentInvite(BaseModel):
    code: str       # Partition Key — 8-char random token
    parent_id: str
    expires_at: str  # ISO timestamp
    used: bool = False

    def to_item(self):
        return self.model_dump()
