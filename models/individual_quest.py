from pydantic import BaseModel
from typing import List

class IndividualQuest(BaseModel):
    week: int
    description: str
    grade: str
    feedback: str
    skills: str
    due_date: str
