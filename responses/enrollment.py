from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from responses.period import PeriodOut


class EnrollResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class StudentItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: Optional[str] = None
    period_id: Optional[str] = None
    semester: Optional[str] = None
    enrolled_at: Optional[str] = None


class EnrollmentsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    students: list[StudentItem]
    file_urls: list[str] = []


class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    interest: Optional[str] = None
    strength: Optional[str] = None
    weakness: Optional[str] = None
    learning_style: Optional[str] = None


class MyPeriodItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_id: str
    name: str
    file_urls: list[str] = []
    long_term_goal: Optional[Any] = None
    is_summer_quest: bool = False


class MyPeriodsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Returned as a top-level list — wrap in a dict for the response_model
    periods: list[MyPeriodItem]


class VerifyPeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut


class UnenrollResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period_id: str
    remaining_enrollments: list[str] = []


class ParentPeriodsListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    periods: list[PeriodOut]


class AcceptInviteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    student_id: Optional[str] = None
    parent_id: Optional[str] = None
    vpc_verified_at: Optional[str] = None
    already_linked: Optional[bool] = None
