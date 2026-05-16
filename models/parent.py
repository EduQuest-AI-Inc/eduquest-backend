from typing import List, Optional

from pydantic import BaseModel, field_validator

from models.user import User

_MAX_INTERESTS = 20
_MAX_INTEREST_LEN = 50
_MAX_NAME_LEN = 100


class Parent(User):
    role: str = 'parent'
    linked_student_ids: List[str] = []
    vpc_verified_at: Optional[str] = None


class CreateStudentProfileRequest(BaseModel):
    name: str
    grade: int
    interests: List[str]

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Name must not be empty')
        if len(v) > _MAX_NAME_LEN:
            raise ValueError(f'Name must be {_MAX_NAME_LEN} characters or fewer')
        return v

    @field_validator('grade')
    @classmethod
    def grade_in_range(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError('Grade must be between 1 and 12')
        return v

    @field_validator('interests')
    @classmethod
    def interests_valid(cls, v: List[str]) -> List[str]:
        cleaned = [i.strip() for i in v if i.strip()]
        if not cleaned:
            raise ValueError('At least one interest is required')
        if len(cleaned) > _MAX_INTERESTS:
            raise ValueError(f'Maximum {_MAX_INTERESTS} interests allowed')
        for item in cleaned:
            if len(item) > _MAX_INTEREST_LEN:
                raise ValueError(f'Each interest must be {_MAX_INTEREST_LEN} characters or fewer')
        seen: set[str] = set()
        deduped: List[str] = []
        for item in cleaned:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped
