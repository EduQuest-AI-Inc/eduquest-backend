from typing import Optional
from pydantic import BaseModel


class AdaptiveSession(BaseModel):
    session_id: Optional[str] = None  # DB-generated UUID
    learner_id: str
    period_id: str
    session_type: str  # pretest | teaching_loop
    status: str = "active"  # active | completed | abandoned
    started_at: Optional[str] = None  # DB-generated
    completed_at: Optional[str] = None
    metadata: Optional[dict] = None

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "AdaptiveSession":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
