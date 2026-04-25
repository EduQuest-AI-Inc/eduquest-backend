from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class LtgConversation(BaseModel):
    user_id: str
    period_id: str
    conversation_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_response_id: Optional[str] = None

    def to_item(self):
        return self.model_dump()
