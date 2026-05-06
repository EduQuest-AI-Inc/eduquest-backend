from pydantic import BaseModel


class Lesson(BaseModel):
    period_id: str
    lesson_name: str
    week_number: int

    def to_item(self):
        return self.model_dump()
