from typing import Optional

from pydantic import BaseModel, ConfigDict


class MembershipSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    plan: Optional[str] = None
    has_active_membership: bool
    trial_ends_at: Optional[str] = None
    class_limit: Optional[int] = None
    students_per_class_limit: Optional[int] = None


class UserProfileResponse(BaseModel):
    """
    Returned by GET /user/profile. Fields vary by role; all declared Optional
    so Pydantic doesn't reject profiles that lack role-specific columns.
    extra="allow" passes through any additional role-specific fields.
    """
    model_config = ConfigDict(extra="allow")

    role: str

    # Common identity fields
    user_id: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    created_at: Optional[str] = None

    # Student-specific
    grade: Optional[str] = None
    strength: Optional[str] = None
    weakness: Optional[str] = None
    interest: Optional[str] = None
    learning_style: Optional[str] = None
    completed_tutorial: Optional[bool] = None

    # Teacher-specific
    pilot_approved: Optional[bool] = None

    # Teacher/parent membership snapshot
    membership: Optional[MembershipSnapshot] = None


class TutorialStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    completed_tutorial: Optional[bool] = None


class UpdateTutorialResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
