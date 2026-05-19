from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class QuestOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    quest_id: str
    user_id: str
    period_id: str
    description: str
    grade: Optional[Any] = None
    feedback: Optional[str] = None
    skills: str
    week: int
    instructions: Any = []
    rubric: Any = {}
    status: str = "not_started"
    completed_steps: list[int] = []
    created_at: Optional[str] = None
    due_date: Optional[str] = None
    last_updated_at: Optional[str] = None
    # Fields appended by QuestRetrievalService.attach_grade_display
    grade_info: Optional[Any] = None
    display_grade: Optional[str] = None


class UpdateStepsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    quest_id: str
    completed_steps: list[int]


class QuestStatusUpdateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    quest_id: str
    status: str


class GradeQuestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    quest_id: str
