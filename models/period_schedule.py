from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


class ConceptNode(TypedDict, total=False):
    """
    Expected shape of a concept inside `period_schedule.schedule_json`.

    The cofounder's class-creation agent emits weeks → lessons → concepts.
    Every field is optional at the type level — the curriculum parser
    tolerates missing fields and the schema is allowed to evolve. Defaults
    are applied at read time, not enforced at write time.
    """
    concept_id: str
    name: str
    prerequisites: List[str]
    skills: List[str]
    mastery_threshold: float
    acceptance_criteria: str
    cognitive_load: Literal["low", "medium", "high"]
    source_reference: str


class PeriodSchedule(BaseModel):
    """
    Stores the master schedule for a period (one schedule per period).
    This is teacher/period scoped, not student scoped.

    `schedule_json` is intentionally untyped here. The expected shape is:

        {
          "weeks": [
            {
              "week": 1,
              "lessons": [
                {
                  "lesson_id": "...",
                  "concepts": [ <ConceptNode>, ... ]
                }
              ]
            }
          ]
        }

    Use `services.knowledge_graph.curriculum_parser` to extract concepts
    and skills — never reach into `schedule_json` directly.
    """
    model_config = {"extra": "ignore"}

    period_id: str  # Partition Key
    schedule_json: Optional[Dict[str, Any]] = None
    schedule_openai_file_id: Optional[str] = None
    quest_enabled_weeks: List[int] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump()

    @classmethod
    def from_item(cls, item: dict):
        return cls(**item)
