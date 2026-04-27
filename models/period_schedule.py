from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone


class PeriodSchedule(BaseModel):
    """
    Stores the master schedule for a period (one schedule per period).
    This is teacher/period scoped, not student scoped.
    """
    period_id: str  # Partition Key
    schedule_json: Optional[Dict[str, Any]] = None
    schedule_openai_file_id: Optional[str] = None  # OpenAI file ID for vector store
    quest_enabled_weeks: List[int] = []  # Weeks where quests are enabled
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()

    @classmethod
    def from_item(cls, item: dict):
        return cls(**item)
