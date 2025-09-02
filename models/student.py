from pydantic import BaseModel
from typing import List, Optional, Dict


class Student(BaseModel):
    student_id: str  # Partition Key
    first_name: str
    last_name: str
    email: str
    email_verified: bool = False
    email_verification_code: Optional[str] = None
    email_verification_expires_at: Optional[str] = None
    enrollments: Optional[List[str]] = []
    grade: int
    strength: Optional[list] = None
    weakness: Optional[list] = None
    interest: Optional[list] = None
    learning_style: Optional[list] = None
    long_term_goal: Optional[Dict[str, str]] = []
    quests: Optional[List[Dict[str, str]]] = []
    password: str
    completed_tutorial: Optional[bool] = False  # New field for tutorial tracking

    def to_item(self):
        return self.model_dump()
