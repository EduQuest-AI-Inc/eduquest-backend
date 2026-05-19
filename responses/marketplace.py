from typing import Optional

from pydantic import BaseModel, ConfigDict

from responses.period import PeriodOut


class MarketplaceListingOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: str
    period_id: str
    published_by: str
    tags: list[str] = []
    fork_count: int = 0
    is_published: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Flattened period fields present in list results (absent in publish response)
    period_name: Optional[str] = None
    period_grade_level: Optional[str] = None
    period_description: Optional[str] = None


class SafePeriodOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_id: str
    name: Optional[str] = None
    grade_level: Optional[str] = None
    course_description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    is_summer_quest: Optional[bool] = None
    created_at: Optional[str] = None
    forked_from_period_id: Optional[str] = None


class MarketplaceListingDetailOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: str
    period_id: str
    published_by: str
    tags: list[str] = []
    fork_count: int = 0
    is_published: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    period: Optional[SafePeriodOut] = None


class ForkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
