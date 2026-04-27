from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime, timezone


class Quest(BaseModel):
    quest_id: str
    user_id: str
    period_id: str
    description: str
    grade: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Grade data as a dict with detailed_grade (rubric breakdown) and overall_score (summary).",
    )
    feedback: Optional[str] = Field(default=None)
    skills: str = Field(description="Skills the student will practice through this quest")
    week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Dict[str, Any] = Field(description="Grading criteria and expectations for the quest")
    status: Literal["not_started", "in_progress", "completed"] = Field(default="not_started")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    due_date: Optional[str] = None
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
