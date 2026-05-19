from typing import Optional

from pydantic import BaseModel, ConfigDict

from responses.period import PeriodOut


class TeacherPeriodsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    periods: list[PeriodOut]


class CanvasCourseOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str


class CanvasCoursesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    courses: list[CanvasCourseOut]


class SkillMasteryOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    week: Optional[int] = None
    skill_name: Optional[str] = None
    percentage: Optional[float] = None
    updated_at: Optional[str] = None
