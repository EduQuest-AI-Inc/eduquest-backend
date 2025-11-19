from pydantic import BaseModel, Field
from datetime import datetime, timezone

class WeeklyQuest(BaseModel):
    quest_id: str  # Partition Key
    student_id: str
    period_id: str
    student_period_key: str = None  # Composite key for GSI: "student_id#period_id"
    year: int = Field(default_factory=lambda: datetime.now(timezone.utc).year)
    semester: str = "Fall 2025"  # Default semester
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()

    @classmethod
    def from_item(cls, item: dict):
        return cls(**item)
