from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from models.weekly_quest_item import WeeklyQuestItem

class WeeklyQuest(BaseModel):
    quest_id: str  # Partition Key
    user_id: str
    period_id: str
    student_period_key: Optional[str] = None  # DynamoDB-only composite key for GSI
    quests: Optional[List[WeeklyQuestItem]] = None  # DynamoDB-only embedded list; Supabase uses individual_quest table
    year: int = Field(default_factory=lambda: datetime.now(timezone.utc).year)
    semester: str = "Fall 2025"  # Default semester
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        item = self.model_dump()
        item['quests'] = [quest.to_dict() for quest in self.quests]
        return item

    @classmethod
    def from_item(cls, item: dict):
        quests_data = item.get('quests', [])
        quests = [WeeklyQuestItem(**quest_data) for quest_data in quests_data]
        item['quests'] = quests
        return cls(**item)
