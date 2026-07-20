from typing import Optional
from pydantic import BaseModel


class CanonicalSkill(BaseModel):
    canonical_skill_id: Optional[str] = None  # DB-generated UUID
    name: str
    normalized_name: Optional[str] = None  # GENERATED ALWAYS AS; read-only
    description: Optional[str] = None
    domain: Optional[str] = None
    embedding: Optional[list[float]] = None  # 1536-dim vector
    created_at: Optional[str] = None  # DB-generated

    def to_item(self) -> dict:
        # Exclude generated/computed columns so Postgres doesn't reject them on INSERT
        return self.model_dump(exclude_none=True, exclude={"normalized_name", "created_at"})

    @classmethod
    def from_item(cls, d: dict) -> "CanonicalSkill":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
