from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timezone

from models.individual_quest import IndividualQuest

class WeeklyQuest(BaseModel):
    weekly_quest_id: str  # Partition Key
    student_id: str
    year: int
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    quests: List[IndividualQuest]

    def to_item(self):
        item = self.model_dump()
        # Convert each IndividualQuest to dict
        item['quests'] = [q.model_dump() for q in self.quests]
        return item
