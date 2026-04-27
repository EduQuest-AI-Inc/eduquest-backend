from typing import List

from models.user import User


class Parent(User):
    role: str = 'parent'
    linked_user_ids: List[str] = []
