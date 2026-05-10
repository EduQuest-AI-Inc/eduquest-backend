from typing import Any, Optional

from pydantic import BaseModel


class PeriodSchedule(BaseModel):
    period_id: str
    schedule_json: Optional[dict[str, Any]] = None

    def to_item(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_item(cls, item: dict) -> "PeriodSchedule":
        return cls(**item)
