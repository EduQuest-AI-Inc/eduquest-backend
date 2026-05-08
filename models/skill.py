from pydantic import BaseModel
from typing import Optional


class Skill(BaseModel):
    period_id: str
    skill_name: str
    description: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None
    mastery_threshold: float = 0.8
    mastery_criteria: Optional[list[dict]] = None
    metadata: Optional[dict] = None

    def to_item(self):
        return self.model_dump()
