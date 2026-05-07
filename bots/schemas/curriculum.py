from typing import Optional
from pydantic import BaseModel


class CurriculumSkill(BaseModel):
    skill_id: str
    title: str
    description: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None
    mastery_threshold: float = 0.8


class CurriculumConcept(BaseModel):
    concept_id: str
    title: str
    description: Optional[str] = None
    prerequisites: list[str] = []
    key_takeaways: list[str] = []
    common_misconceptions: list[str] = []
    skills: list[CurriculumSkill]


class CurriculumLesson(BaseModel):
    lesson_id: str
    title: str
    concepts: list[CurriculumConcept]


class CurriculumWeek(BaseModel):
    week_number: int
    week_id: str
    title: str
    lessons: list[CurriculumLesson]


class CurriculumResult(BaseModel):
    grade_level: str
    course: str
    total_weeks: int
    weeks: list[CurriculumWeek]
