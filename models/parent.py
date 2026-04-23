from typing import List

from models.user import User


class Parent(User):
    role: str = 'parent'
    linked_student_ids: List[str] = []
