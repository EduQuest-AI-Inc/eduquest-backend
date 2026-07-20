from typing import Optional
from pydantic import BaseModel


class Misconception(BaseModel):
    misconception_id: Optional[str] = None  # DB-generated UUID
    canonical_skill_id: str
    signature: str
    remediation_strategy: str
    source_confidence: str = "seeded"  # seeded | verified
    created_at: Optional[str] = None  # DB-generated

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "Misconception":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
