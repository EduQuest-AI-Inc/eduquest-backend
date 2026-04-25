from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AggregatedMetrics(BaseModel):
    period_id: str
    week: int
    skill_name: str
    percentage: float
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
