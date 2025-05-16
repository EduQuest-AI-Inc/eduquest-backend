from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum

class Role(str, Enum):
    student = "student"
    teacher = "teacher"

class Session(BaseModel):
    session_id: str
    last_login: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    role: Role
    auth_token: str
    user_id: str

    def to_item(self):
        return self.model_dump()
