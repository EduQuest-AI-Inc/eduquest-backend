from pydantic import BaseModel
from typing import List, Optional


class Parent(BaseModel):
    parent_id: str  # Partition Key (username)
    first_name: str
    last_name: str
    email: str
    email_lc: Optional[str] = None  # Canonical lowercase email for lookups
    password: str
    linked_student_ids: List[str] = []
    last_login: Optional[str] = None

    def to_item(self):
        return self.model_dump()
