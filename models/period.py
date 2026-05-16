from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import date, datetime, timezone


class CourseMetadata(BaseModel):
    learning_objectives: Optional[str] = None
    primary_standard: Optional[str] = None
    additional_standards: List[str] = []
    specific_standard_codes: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class Period(BaseModel):
    period_id: str
    owner_id: str
    name: str
    vector_store_id: Optional[str] = None
    file_urls: List[str] = []
    canvas_course_id: Optional[int] = None
    canvas_course_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    grade_level: Optional[str] = None
    mastery_threshold: Optional[float] = None
    course_description: Optional[str] = None
    course_metadata: Optional[CourseMetadata] = None
    file_vector_store_ids: List[str] = []
    processing_status: str = "pending"
    status: str = "pending"
    is_summer_quest: bool = False
    forked_from_period_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self):
        return self.model_dump(mode='json')
