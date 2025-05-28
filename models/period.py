from pydantic import BaseModel

class Period(BaseModel):
    period_id: str  # Partition Key
    initial_conversation_assistant_id: str
    update_assistant_id: str
    teacher_id: str
    vector_store_id: str
    course: str

    def to_item(self):
        return self.model_dump()
