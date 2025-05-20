from pydantic import BaseModel
from canvas import Course


class Period(BaseModel):
    period_id: str
    initial_conversation_assistant_id: str
    update_assistant_id: str
    teacher_id: str
    vector_store_id: str
    course: str