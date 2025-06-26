from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, timezone

class IndividualQuest(BaseModel):
    individual_quest_id: str  
    quest_id: str  
    student_id: str
    period_id: str
    description: str
    grade: Optional[str] = Field(default=None, description="Grade provided by the grader")
    feedback: Optional[str] = Field(default=None, description="Feedback provided by the grader")
    skills: str = Field(description="Skills the student will practice through this quest")
    week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Dict[str, Any] = Field(description="Grading criteria and expectations for the quest")
    status: Literal["not_started", "in_progress", "completed"] = Field(default="not_started", description="Status of the quest")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    due_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
      
    def to_item(self):
        return self.model_dump()

