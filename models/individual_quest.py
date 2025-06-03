from pydantic import BaseModel, Field
from typing import List

class IndividualQuest(BaseModel):
    quest_id: str  # Partition Key
    description: str
    grade: str = Field(description="Grade provided by the grader")
    feedback: str = Field(description="Feedback provided by the grader")
    skills: str = Field(description="Skills the student will practice through this quest")
    created_at: str
    due_date: str  
      
    def to_item(self):
        return self.model_dump()

