from pydantic import BaseModel
from typing import Optional


class Teacher(BaseModel):
    teacher_id: str  # Partition Key
    first_name: str
    last_name: str
    email: str
    email_lc: Optional[str] = None  # Canonical lowercase email for lookups
    password: str
    last_login: Optional[str] = None
    pilot_approved: bool = False  # Whether teacher is approved for pilot study

    def to_item(self):
        return self.model_dump()
