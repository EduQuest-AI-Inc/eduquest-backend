from typing import Optional
from pydantic import BaseModel


class LearnerSkillState(BaseModel):
    learner_id: str
    canonical_skill_id: str
    mastery: float = 0.0
    confidence: float = 0.0
    last_verified_at: Optional[str] = None
    evidence_count: int = 0

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "LearnerSkillState":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
