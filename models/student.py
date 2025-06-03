from pydantic import BaseModel
from typing import List, Optional, Dict


class Student(BaseModel):
    student_id: str  # Partition Key
    first_name: str
    last_name: str
    enrollments: Optional[List[str]]
    grade: int
    strength: Optional[list] = None
    weakness: Optional[list] = None
    interest: Optional[list] = None
    learning_style: Optional[list] = None
    long_term_goal: Optional[List[Dict[str, str]]] = []
    quests: Optional[List[Dict[str, str]]] = []
    grade: Optional[int] = None
    # def to_item(self):
    #     return self.model_dump()
