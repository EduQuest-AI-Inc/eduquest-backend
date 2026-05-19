from pydantic import BaseModel, ConfigDict


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
