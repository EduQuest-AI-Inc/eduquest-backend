from typing import Optional

from pydantic import BaseModel, ConfigDict


class LessonPptxResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    expires_in: int
    version: int
    lesson_name: Optional[str] = None


class RegenerateLessonResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pptx_id: str


class LessonHtmlResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    expires_in: int
