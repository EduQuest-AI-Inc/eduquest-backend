from pydantic import BaseModel
from typing import Optional


class Concept(BaseModel):
    period_id: str
    concept_name: str
    lesson_name: str
    description: Optional[str] = None
    prerequisites: Optional[list[dict]] = None
    common_misconceptions: Optional[list[dict]] = None
    key_takeaways: Optional[list[dict]] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None
    last_updated_at: Optional[str] = None

    def to_item(self):
        return self.model_dump(exclude={'created_at', 'last_updated_at'})
