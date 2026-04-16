from pydantic import BaseModel
from typing import List, Optional

class Period(BaseModel):
    period_id: str      # Partition Key
    owner_id: str       # The user who owns this period (teacher_id or parent_id)
    owner_type: str = "teacher"  # "teacher" | "parent"
    vector_store_id: str
    course: str
    file_urls: List[str] = []
    canvas_api_url: Optional[str] = None
    canvas_api_key: Optional[str] = None
    canvas_course_id: Optional[int] = None
    canvas_course_name: Optional[str] = None
    # Kept for backward compat — populated for teacher-owned periods only
    teacher_id: Optional[str] = None
    parent_id: Optional[str] = None

    def to_item(self):
        return self.model_dump()
