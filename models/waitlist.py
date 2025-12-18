from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


def _generate_referral_code() -> str:
    """Generate an 8-character uppercase referral code"""
    return uuid.uuid4().hex[:8].upper()


@dataclass
class PilotWaitlistEntry:
    """
    Represents a teacher's entry in the pilot study waitlist.
    Teachers join after signup to request access to create classes.
    
    DynamoDB Key Schema:
    - Partition Key: waitlistID (stores teacher_id)
    - Sort Key: email (stores teacher's email)
    """
    teacher_id: str  # Stored in waitlistID field (DynamoDB partition key)
    email: str       # DynamoDB sort key (required)
    joined_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    position: int = 0  # Position in the waitlist queue
    referral_code: str = field(default_factory=_generate_referral_code)
    referred_by: Optional[str] = None  # Teacher ID of who referred them
    status: str = "pending"  # "pending" or "approved"

    def to_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format"""
        item = {
            "waitlistID": self.teacher_id,          # PK - stores teacher_id
            "email": self.email.strip().lower(),    # SK - required by table schema
            "joinedAt": self.joined_at,
            "position": self.position,
            "referralCode": self.referral_code,
            "status": self.status,
        }
        if self.referred_by:
            item["referredBy"] = self.referred_by
        return item

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> "PilotWaitlistEntry":
        """Create instance from DynamoDB item"""
        return cls(
            teacher_id=item.get("waitlistID", ""),
            email=item.get("email", ""),
            joined_at=item.get("joinedAt", ""),
            position=item.get("position", 0),
            referral_code=item.get("referralCode", ""),
            referred_by=item.get("referredBy"),
            status=item.get("status", "pending"),
        )
