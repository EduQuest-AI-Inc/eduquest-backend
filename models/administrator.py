from pydantic import BaseModel
from typing import Optional

class Administrator(BaseModel):
    admin_id: str
    first_name: str
    last_name: str
    email: str
    school_id: str
    password: str
    last_login: Optional[str] = None

    def to_item(self):
        return self.model_dump()
