from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime, timedelta, timezone


def default_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()


class Session(BaseModel):
    auth_token: str
    user_id: str
    role: Literal["student", "teacher", "parent"]
    expires_at: str = Field(default_factory=default_expiry)

    def to_item(self):
        return self.model_dump(exclude_none=True)
