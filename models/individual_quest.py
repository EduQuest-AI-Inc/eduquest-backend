from pydantic import BaseModel, Field

class IndividualQuest(BaseModel):
    quest_id: str  # Partition Key
    Description: str
    Grade: str = Field(description="Grade provided by the grader")
    Feedback: str = Field(description="Feedback provided by the grader")
    Skills: str = Field(description="Skills the student will practice through this quest")
    created_at: str

    def to_item(self):
        return self.model_dump()
