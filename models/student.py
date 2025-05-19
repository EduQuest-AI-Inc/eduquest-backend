from pydantic import BaseModel
from typing import List

class Student(BaseModel):
    student_id: str  # Partition Key
    first_name: str
    last_name: str
    enrollments: List[str]
    grade: int
    strenth: str
    weakness: str
    interest: str
    learning_style: str
    long_term_goal: str
    last_login: str
    password: str

    def to_item(self):
        return self.model_dump()
