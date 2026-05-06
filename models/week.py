from pydantic import BaseModel
from typing import Optional
from datetime import date


class Week(BaseModel):
    period_id: str
    week_number: int
    week_start: Optional[date] = None
    week_end: Optional[date] = None

    def to_item(self):
        return self.model_dump(mode='json')
