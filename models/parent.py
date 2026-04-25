from typing import List, Optional

from models.user import User


class Parent(User):
    role: str = 'parent'
    linked_student_ids: List[str] = []
    created_at: Optional[str] = None
    vpc_verified_at: Optional[str] = None
