from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: str
    password: str
    last_login: Optional[str] = None
    role: str
    canvas_api_url: Optional[str] = None
    canvas_api_key: Optional[str] = None

    def to_item(self):
        return self.model_dump()
