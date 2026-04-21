from pydantic import BaseModel
from typing import List, Optional

class Period(BaseModel):
    period_id: str      # Partition Key
    owner_id: str       # The user_id of the teacher or parent who owns this period
    owner_type: str = "teacher"  # "teacher" | "parent"
    vector_store_id: str
    course: str
    file_urls: List[str] = []
    canvas_api_url: Optional[str] = None
    canvas_api_key: Optional[str] = None
    canvas_course_id: Optional[int] = None
    canvas_course_name: Optional[str] = None

    def to_item(self):
        return self.model_dump()
