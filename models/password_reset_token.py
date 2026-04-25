from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone


def default_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()


class PasswordResetToken(BaseModel):
    token_hash: str
    user_id: str
    email: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = Field(default_factory=default_expires_at)
    used_at: Optional[str] = None
    burned_at: Optional[str] = None
    attempts: int = 0
    request_ip: Optional[str] = None
    user_agent: Optional[str] = None

    def to_item(self):
        return self.model_dump(exclude_none=True)

