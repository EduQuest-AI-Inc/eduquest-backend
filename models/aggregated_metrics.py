from pydantic import BaseModel, Field
from typing import List
from decimal import Decimal


class SkillMetric(BaseModel):
    skill_name: str = Field(description="Name of the skill")
    percentage: int = Field(description="Mastery percentage (0-100)")


class WeekMetrics(BaseModel):
    skills: List[SkillMetric] = Field(
        default_factory=list,
        description="Skills assessed during this week",
    )


class AggregatedMetrics(BaseModel):
    course_week: str = Field(description="Partition key (same as period_id)")
    weeks: List[WeekMetrics] = Field(
        default_factory=list,
        description="Per-week skill metrics, ordered by week number",
    )

    def to_dynamo_item(self) -> dict:
        return {
            "course-week": self.course_week,
            "Weeks": [
                [
                    {"skill name": s.skill_name, "percentage": s.percentage}
                    for s in week.skills
                ]
                for week in self.weeks
            ],
        }

    @classmethod
    def from_dynamo_item(cls, item: dict) -> "AggregatedMetrics":
        raw_weeks = item.get("Weeks", [])
        weeks: List[WeekMetrics] = []
        for raw_week in raw_weeks:
            skills = []
            for raw_skill in raw_week:
                pct = raw_skill.get("percentage", 0)
                if isinstance(pct, Decimal):
                    pct = int(pct)
                skills.append(SkillMetric(
                    skill_name=raw_skill.get("skill name", ""),
                    percentage=int(pct),
                ))
            weeks.append(WeekMetrics(skills=skills))
        return cls(
            course_week=item["course-week"],
            weeks=weeks,
        )
