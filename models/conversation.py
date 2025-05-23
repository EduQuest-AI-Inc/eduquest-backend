from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Literal

class Conversation(BaseModel):
    thread_id: str
    user_id: str
    role: Literal["student", "teacher"]
    conversation_type: str
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    period_id: str

    def to_item(self):
        return self.model_dump()
