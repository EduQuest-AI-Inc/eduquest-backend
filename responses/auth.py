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

    access_token: str
    refresh_token: str
    needs_profile: Optional[bool] = None


class OAuthCompleteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    needs_profile: Optional[bool] = None


class PasswordResetRequestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class PasswordResetConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class AgeScreenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    age_band: str
    next_step: str


class StudentEmailRequestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class StudentEmailConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class DeleteAccountResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
