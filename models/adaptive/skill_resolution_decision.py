from typing import Optional
from pydantic import BaseModel


class SkillResolutionDecision(BaseModel):
    id: Optional[str] = None  # DB-generated UUID
    period_id: str
    skill_name: str
    canonical_skill_id: Optional[str] = None
    outcome: str  # exact | embedding | llm_judge | minted
    similarity_score: Optional[float] = None
    judge_rationale: Optional[str] = None
    created_at: Optional[str] = None  # DB-generated

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "SkillResolutionDecision":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
