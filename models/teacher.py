from pydantic import BaseModel

class Teacher(BaseModel):
    teacher_id: str  # Partition Key
    first_name: str
    last_name: str
    email: str
    last_login: str = None
    password: str

    def to_item(self):
        return self.model_dump()
