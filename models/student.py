from typing import Optional

from models.user import User


class Student(User):
    role: str = 'student'
    grade: Optional[int] = None
    strength: Optional[list[str]] = None
    weakness: Optional[list[str]] = None
    interest: Optional[list[str]] = None
    learning_style: Optional[list[str]] = None
    completed_tutorial: bool = False
    school_name: Optional[str] = None
    account_status: str = 'active'
    created_by_parent_id: Optional[str] = None
    claimed_at: Optional[str] = None
    age_band: Optional[str] = None
    age_signal_source: Optional[str] = None
    compliance_status: str = 'blocked'
    compliance_review_due_at: Optional[str] = None
    compliance_outreach_stage: int = 0
    compliance_outreach_sent_at: Optional[str] = None
