"""
Password reset token model for EduQuest.
"""

from pydantic import BaseModel, Field
from typing import Optional
import time


def default_expires_at():
    """Token expires in 45 minutes (2700 seconds)."""
    return int(time.time()) + 2700


class PasswordResetToken(BaseModel):
    token_hash: str  # Partition Key - SHA-256 hash of the actual token
    user_id: str  # student_id or teacher_id
    role: str  # 'student' or 'teacher'
    email_lc: str  # Canonical lowercase email
    created_at_iso: str  # ISO format timestamp
    expires_at_epoch: int = Field(default_factory=default_expires_at)  # TTL attribute
    used_at_iso: Optional[str] = None  # Set when token is consumed
    burned_at_iso: Optional[str] = None  # Set when token is burned (too many attempts)
    attempts: int = 0  # Number of confirmation attempts
    request_ip: Optional[str] = None  # IP address that requested the reset
    user_agent: Optional[str] = None  # User-Agent header from request

    def to_item(self):
        return self.model_dump(exclude_none=True)

