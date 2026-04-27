from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class Enrollment(BaseModel):
    enrollment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    period_id: str
    enrolled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str
    semester: str

    def to_item(self):
        return self.model_dump()
