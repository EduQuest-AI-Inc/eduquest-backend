from typing import Optional
from pydantic import BaseModel


class LessonPptx(BaseModel):
    lesson_id: str
    period_id: str
    status: str = 'pending'
    s3_key: Optional[str] = None
    pptx_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_item(self) -> dict:
        return self.model_dump(exclude={'pptx_id', 'created_at', 'updated_at'})
