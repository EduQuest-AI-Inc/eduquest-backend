from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone

class WeeklyQuestItem(BaseModel):
    individual_quest_id: str  # Individual quest ID within the weekly quest list
    name: str
    skills: str
    week: int
    status: str = "not_started"
    description: Optional[str] = None
    instructions: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    grade: Optional[str] = None
    feedback: Optional[str] = None
    due_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return self.model_dump() 