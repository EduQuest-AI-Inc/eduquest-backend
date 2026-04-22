from typing import List, Optional, Dict

from models.user import User


class Student(User):
    role: str = 'student'
    grade: int
    strength: Optional[list] = None
    weakness: Optional[list] = None
    interest: Optional[list] = None
    learning_style: Optional[list] = None
    completed_tutorial: Optional[bool] = False
    school_id: Optional[str] = None
    # These live in related tables, not the student table itself
    enrollments: Optional[List[str]] = []
    long_term_goal: Optional[Dict[str, str]] = []
    quests: Optional[List[Dict[str, str]]] = []
