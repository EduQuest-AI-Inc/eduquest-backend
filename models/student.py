from typing import Optional

from models.user import User


class Student(User):
    role: str = 'student'
    grade: Optional[int] = None
    strength: Optional[list] = None
    weakness: Optional[list] = None
    interest: Optional[list] = None
    learning_style: Optional[str] = None
    completed_tutorial: bool = False
    school_name: Optional[str] = None
    created_at: Optional[str] = None
