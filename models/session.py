from pydantic import BaseModel
from typing import Literal

class Session(BaseModel):
    auth_token: str  # Partition key
    user_id: str     # Sort key
    role: Literal["student", "teacher"]

    def to_item(self):
        return self.model_dump()
