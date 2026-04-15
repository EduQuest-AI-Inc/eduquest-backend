from pydantic import BaseModel
from typing import List, Optional

class Period(BaseModel):
    period_id: str  # Partition Key
    teacher_id: str
    vector_store_id: str
    course: str
    file_urls: List[str] = []
    canvas_api_url: Optional[str] = None
    canvas_api_key: Optional[str] = None
    canvas_course_id: Optional[int] = None
    canvas_course_name: Optional[str] = None

    def to_item(self):
        return self.model_dump()
