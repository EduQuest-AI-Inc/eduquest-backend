from typing import Any, Dict, List

from pydantic import BaseModel


class SkillMetric(BaseModel):
    percentage: float
    skill_name: str


class WeekMetrics(BaseModel):
    skills: List[SkillMetric]


class AggregatedMetrics(BaseModel):
    """
    Pydantic representation of an item in the aggregated-metrics DynamoDB table.

    DynamoDB (as shown in the console) represents an item like:

    {
      "course-week": { "S": "aksdjn;asdjnf" },
      "Weeks": {
        "L": [
          {
            "L": [
              { "M": { "percentage": { "N": "95" }, "skill name": { "S": "can do integrals" } } },
              ...
            ]
          },
          ...
        ]
      }
    }

    At the Python level (what the DAO reads/writes), this is treated as:

    {
      "course-week": "aksdjn;asdjnf",
      "Weeks": [
        [
          {"percentage": 95, "skill name": "can do integrals"},
          ...
        ],
        ...
      ]
    }
    """

    course_week: str
    weeks: List[WeekMetrics]

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "AggregatedMetrics":
        """
        Convert a raw DynamoDB item (using the attribute names actually stored
        in the table) into the structured AggregatedMetrics model.
        """
        course_week = item["course-week"]
        weeks_raw = item.get("Weeks", [])

        weeks: List[WeekMetrics] = []
        for week_list in weeks_raw:
            skills: List[SkillMetric] = []
            for skill_raw in week_list:
                skills.append(
                    SkillMetric(
                        percentage=skill_raw["percentage"],
                        skill_name=skill_raw["skill name"],
                    )
                )
            weeks.append(WeekMetrics(skills=skills))

        return cls(course_week=course_week, weeks=weeks)

    def to_dynamo_item(self) -> Dict[str, Any]:
        """
        Convert this AggregatedMetrics instance into the shape expected by the
        aggregated-metrics DynamoDB table.
        """
        return {
            "course-week": self.course_week,
            "Weeks": [
                [
                    {
                        "percentage": skill.percentage,
                        "skill name": skill.skill_name,
                    }
                    for skill in week.skills
                ]
                for week in self.weeks
            ],
        }

