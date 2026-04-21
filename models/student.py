from pydantic import BaseModel
from typing import List, Optional, Dict


class Student(BaseModel):
    user_id: str  # Partition Key
    first_name: str
    last_name: str
    email: str
    email_lc: Optional[str] = None  # Canonical lowercase email for lookups
    enrollments: Optional[List[str]] = []
    grade: int
    strength: Optional[list] = None
    weakness: Optional[list] = None
    interest: Optional[list] = None
    learning_style: Optional[list] = None
    long_term_goal: Optional[Dict[str, str]] = []
    quests: Optional[List[Dict[str, str]]] = []
    password: str
    completed_tutorial: Optional[bool] = False
    canvas_api_url: Optional[str] = None
    canvas_api_key: Optional[str] = None

    def to_item(self):
        return self.model_dump()
