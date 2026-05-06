from datetime import datetime, timezone

from pydantic import BaseModel, Field

MASTERY_CUTOFF = 0.70


class StudentSkillMastery(BaseModel):
    student_id: str
    period_id: str
    skill_name: str
    mastered: bool = False
    score: float = 0.0
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_item(cls, item: dict) -> "StudentSkillMastery":
        return cls(**item)
