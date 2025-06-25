from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timezone

from models.weekly_quest_item import WeeklyQuestItem

class WeeklyQuest(BaseModel):
    quest_id: str  # Partition Key - represents one list of quests for a period
    student_id: str
    period_id: str
    quests: List[WeeklyQuestItem]  # List of 18 individual quests
    year: int = Field(default_factory=lambda: datetime.now(timezone.utc).year)
    semester: str = "Fall 2025"  # Default semester
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        # Convert the quests list to a format suitable for DynamoDB
        item = self.model_dump()
        # Convert each quest to a dict for storage
        item['quests'] = [quest.to_dict() for quest in self.quests]
        return item

    @classmethod
    def from_item(cls, item: dict):
        # Convert from DynamoDB item back to model
        quests_data = item.get('quests', [])
        quests = [WeeklyQuestItem(**quest_data) for quest_data in quests_data]
        item['quests'] = quests
        return cls(**item)
