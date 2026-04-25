from typing import Optional

from models.user import User


class Teacher(User):
    role: str = 'teacher'
    pilot_approved: bool = False
    school_name: Optional[str] = None
    created_at: Optional[str] = None
