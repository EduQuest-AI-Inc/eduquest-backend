from pydantic import BaseModel, Field
from datetime import datetime, timezone


class StudentSkillMastery(BaseModel):
    student_id: str
    period_id: str
    skill_name: str
    mastered: bool
    score: float
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
