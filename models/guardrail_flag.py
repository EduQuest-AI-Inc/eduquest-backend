from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional

class GuardrailFlag(BaseModel):
    flag_id: str
    student_id: str
    period_id: str
    flagged_content: str
    guardrail_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: bool = False
    admin_notes: Optional[str] = None

    def to_item(self):
        return self.model_dump()
