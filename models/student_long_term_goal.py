from pydantic import BaseModel, Field
from datetime import datetime, timezone


class StudentLongTermGoal(BaseModel):
    user_id: str
    period_id: str
    goal_text: str
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
