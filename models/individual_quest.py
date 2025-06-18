from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from models.rubric import Rubric

class IndividualQuest(BaseModel):
    quest_id: str  # Partition Key
    description: str
    grade: Optional[str] = Field(description="Grade provided by the grader")
    feedback: Optional[str] = Field(description="Feedback provided by the grader")
    skills: str = Field(description="Skills the student will practice through this quest")
    Week: int = Field(description="Week the student will work on this quest")
    instructions: str = Field(description="Detailed instructions for completing the quest")
    rubric: Rubric = Field(description="Grading criteria and expectations for the quest")
    status: Literal["not_started", "in_progress", "completed"] = Field(description="Status of the quest")
    created_at: str
    due_date: str  
      
    def to_item(self):
        return self.model_dump()

