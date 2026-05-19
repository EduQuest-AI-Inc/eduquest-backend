from pydantic import BaseModel, ConfigDict


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class CurriculumStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_status: str


class ApprovePeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_lessons: int
