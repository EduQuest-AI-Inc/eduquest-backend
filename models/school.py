from pydantic import BaseModel
from typing import List

class School(BaseModel):
    school_id: str  # Partition Key
    school_name: str
    
    def to_item(self):
        return self.model_dump()
