from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime, timezone

class Conversation(BaseModel):
    thread_id: str
    user_id: str
    role: Literal["student", "teacher"]
    conversation_type: str
    period_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), alias="createdAt")

    def to_item(self):
        return self.model_dump()
