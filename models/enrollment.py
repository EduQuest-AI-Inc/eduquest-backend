from pydantic import BaseModel, Field
from datetime import datetime, timezone

class Enrollment(BaseModel):
    period_id: str              # PK
    enrolled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # SK
    student_id: str
    semester: str
    
    def to_item(self):
        return self.model_dump()