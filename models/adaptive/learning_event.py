from typing import Optional
from pydantic import BaseModel


class LearningEvent(BaseModel):
    event_id: Optional[str] = None  # DB-generated UUID
    learner_id: str
    canonical_skill_id: Optional[str] = None
    event_type: str  # artifact_seed | pretest | loop_attempt | embedded_check
    result: str  # correct | incorrect | partial | seeded
    misconception_id: Optional[str] = None
    raw_evidence_summary: Optional[str] = None  # non-PII summary only
    created_at: Optional[str] = None  # DB-generated

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "LearningEvent":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
