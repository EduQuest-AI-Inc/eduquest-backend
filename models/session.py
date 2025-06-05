from pydantic import BaseModel, Field
from typing import Literal
import time

def default_expiry():
    return int(time.time()) + 43200  # 12 hours = 43200 seconds

class Session(BaseModel):
    auth_token: str  # Partition key
    user_id: str     # Sort key
    role: Literal["student", "teacher"]
    expires_at: int = Field(default_factory=default_expiry)  # Defaults to 12 hours

    def to_item(self):
        return self.model_dump()
