from pydantic import BaseModel
from typing import Optional

class Teacher(BaseModel):
    teacher_id: str  # Partition Key
    first_name: str
    last_name: str
    email: str
    email_verified: bool = False
    email_verification_code: Optional[str] = None
    email_verification_expires_at: Optional[str] = None
    last_login: str = None
    password: str

    def to_item(self):
        return self.model_dump()
