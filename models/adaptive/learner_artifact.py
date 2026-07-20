from typing import Optional
from pydantic import BaseModel


class LearnerArtifact(BaseModel):
    artifact_id: Optional[str] = None  # DB-generated UUID
    learner_id: str
    period_id: str
    artifact_type: str  # resume | transcript | free_text | file
    s3_key: Optional[str] = None
    extracted_summary: Optional[str] = None
    delete_after: Optional[str] = None
    deleted_at: Optional[str] = None
    created_at: Optional[str] = None  # DB-generated

    def to_item(self) -> dict:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_item(cls, d: dict) -> "LearnerArtifact":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
