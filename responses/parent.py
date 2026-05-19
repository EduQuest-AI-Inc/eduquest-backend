from typing import Any

from pydantic import BaseModel, ConfigDict

from responses.period import PeriodOut


class ParentMyPeriodsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    periods: list[PeriodOut]


class GenerateInviteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    expires_at: str


class StudentSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    first_name: str
    last_name: str
    grade: int
    email: str
    interest: list[Any] = []


class StudentsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    students: list[StudentSummary]


class EnrollStudentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut


class CreateStudentProfileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    name: str
    grade: int
    interests: list[str] = []
