from pydantic import BaseModel
from typing import Optional


class Concept(BaseModel):
    period_id: str
    concept_name: str
    lesson_name: str
    lesson_id: Optional[str] = None
    description: Optional[str] = None
    prerequisites: Optional[list[str]] = None
    common_misconceptions: Optional[list[str]] = None
    key_takeaways: Optional[list[str]] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None
    last_updated_at: Optional[str] = None

    def to_item(self):
        exclude = {'created_at', 'last_updated_at'}
        if self.lesson_id is None:
            exclude.add('lesson_id')
        return self.model_dump(exclude=exclude)
