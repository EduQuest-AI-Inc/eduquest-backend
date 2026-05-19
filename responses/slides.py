from typing import Optional

from pydantic import BaseModel, ConfigDict


class PptxStatusItemOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pptx_id: str
    lesson_id: str
    lesson_name: Optional[str] = None
    week_number: Optional[int] = None
    pptx_status: str
    attempt_count: int = 0


class RestartResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    queued: int
