from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

class Period(BaseModel):
    period_id: str
    owner_id: str
    name: str
    vector_store_id: Optional[str] = None
    file_urls: List[str] = []
    canvas_course_id: Optional[int] = None
    canvas_course_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
