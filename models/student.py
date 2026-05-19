from typing import Optional

from models.user import User


class Student(User):
    role: str = 'student'
    grade: Optional[int] = None
    strength: Optional[list[str]] = None
    weakness: Optional[list[str]] = None
    interest: Optional[list[str]] = None
    learning_style: Optional[list[str]] = None
    completed_tutorial: bool = False
    school_name: Optional[str] = None
    account_status: str = 'active'
    created_by_parent_id: Optional[str] = None
    claimed_at: Optional[str] = None
