from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List

class Conversation(BaseModel):
    thread_id: str
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    student_id: str
    conversation_type: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
