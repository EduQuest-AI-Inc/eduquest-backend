from pydantic import BaseModel
from typing import List, Optional

class School(BaseModel):
    school_id: str  # Partition Key
    school_name: str
    students: List[str]
    teachers: List[str]
    periods: List[str]
    administrators: Optional[List[str]] = []

    def to_item(self):
        return self.model_dump()
