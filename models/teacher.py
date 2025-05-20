from pydantic import BaseModel

class Teacher(BaseModel):
    teacher_id: str  # Partition Key
    first_name: str
    last_name: str
    last_login: str
    password: str

    def to_item(self):
        return self.model_dump()
