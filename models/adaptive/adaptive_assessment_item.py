from typing import Optional
from pydantic import BaseModel


class AdaptiveAssessmentItem(BaseModel):
    item_id: Optional[str] = None  # DB-generated UUID
    session_id: str
    learner_id: str  # denormalized for efficient history queries by learner+skill
    canonical_skill_id: Optional[str] = None
    prompt: str
    modality: Optional[str] = None  # worked_example | analogy
    learner_answer: Optional[str] = None
    scored_result: Optional[str] = None  # correct | incorrect | partial
    misconception_id: Optional[str] = None
    created_at: Optional[str] = None  # DB-generated

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "AdaptiveAssessmentItem":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
