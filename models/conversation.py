from pydantic import BaseModel, Field
from datetime import datetime, timezone


class Conversation(BaseModel):
    conversation_id: str
    user_id: str
    conversation_type: str
    period_id: str | None = None
    last_response_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
