from pydantic import BaseModel

class IndividualQuest(BaseModel):
    quest_id: str  # Partition Key
    Description: str
    Grade: str
    Feedback: str
    Skills: str
    created_at: str

    def to_item(self):
        return self.model_dump()
