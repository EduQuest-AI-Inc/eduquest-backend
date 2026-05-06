from pydantic import BaseModel


class CurriculumSkill(BaseModel):
    skill_id: str
    title: str


class CurriculumConcept(BaseModel):
    concept_id: str
    title: str
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
