from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PeriodOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_id: str
    name: str
    status: str
    processing_status: str
    owner_id: str
    is_summer_quest: bool
    has_curriculum: Optional[bool] = None
    forked_from_period_id: Optional[str] = None
    file_urls: list[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    grade_level: Optional[str] = None
    mastery_threshold: Optional[float] = None
    course_description: Optional[str] = None
    vector_store_id: Optional[str] = None
    canvas_course_id: Optional[int] = None
    canvas_course_name: Optional[str] = None
    course_metadata: Optional[Any] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    archived_at: Optional[str] = None


class GetPeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period: PeriodOut


class PeriodListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    periods: list[PeriodOut]


class CreatePeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut
    status: str


class UpdatePeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut
    status: str


class ForkMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut


class MultipartInitResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    upload_id: str
    part_urls: list[str]


class MultipartCompleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str


class AddFilesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    added_files: list[str]


class PresignedFileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str


class ArchivePeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut


class UnarchivePeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    period: PeriodOut


class SummerQuestGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
