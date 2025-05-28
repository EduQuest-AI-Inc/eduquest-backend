from pydantic import BaseModel
from typing import List

class WeeklyQuest(BaseModel):
    student_id: str  # Partition Key
    created_at: str  # Sort Key
    # week: int
    year: int
    semester: int
    last_updated_at: str
    quests: List[str]

    def to_item(self):
        return self.model_dump()
