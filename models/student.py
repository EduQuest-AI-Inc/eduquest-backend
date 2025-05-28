from pydantic import BaseModel
from typing import List, Optional

class Student(BaseModel):
    student_id: str  # Partition Key
    first_name: str
    last_name: str
    enrollments: List[str]
    grade: int
    strength: Optional = str
    weakness: Optional = str
    interest: Optional = str
    learning_style: Optional = str
    long_term_goal: str
    last_login: str
    password: str

    # def to_item(self):
    #     return self.model_dump()
