from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class User(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: str
    password: str
    phone_number: Optional[str] = None
    last_login: Optional[str] = None
    role: str
    login_disabled: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()
