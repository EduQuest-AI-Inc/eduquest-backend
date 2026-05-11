from pydantic import BaseModel
from typing import Optional


class Lesson(BaseModel):
    period_id: str
    lesson_name: str
    week_number: int
    lesson_id: Optional[str] = None

    def to_item(self):
        return self.model_dump(exclude={'lesson_id'})
