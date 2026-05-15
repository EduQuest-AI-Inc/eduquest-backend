from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timezone
import uuid


class MarketplaceListing(BaseModel):
    listing_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    period_id: str
    published_by: str
    tags: List[str] = []
    fork_count: int = 0
    is_published: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self) -> dict:
        return self.model_dump()
