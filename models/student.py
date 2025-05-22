from pydantic import BaseModel
from typing import List, Optional

class Student(BaseModel):
    student_id: str  # Partition Key
    first_name: str
    last_name: str
    password: str
    email: str
    last_login: str = None

    enrollments: Optional[List[str]] = []
    strength: Optional[str] = None
    weakness: Optional[str] = None
    interest: Optional[str] = None
    learning_style: Optional[str] = None
    long_term_goal: Optional[str] = None


    def to_item(self):
        return self.model_dump()
