from typing import Optional

from pydantic import BaseModel, ConfigDict


class SignupResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    trial_started: Optional[bool] = None
    parent_linked: Optional[bool] = None
    invite_warning: Optional[str] = None


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str
    needs_profile: Optional[bool] = None


class PasswordResetRequestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class PasswordResetConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
