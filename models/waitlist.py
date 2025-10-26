from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

@dataclass
class Waitlist:
    email: str
    waitlistID: str = field(default_factory=lambda: str(uuid.uuid4()))
    createdAt: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    used: bool = False
    usedAt: Optional[str] = None
    usedBy: Optional[str] = None

    def to_item(self) -> Dict[str, Any]:
        item = {
            "waitlistID": self.waitlistID,
            "email": self.email.strip().lower(),
            "createdAt": self.createdAt,
            "used": self.used,
        }
        if self.usedAt:
            item["usedAt"] = self.usedAt
        if self.usedBy:
            item["usedBy"] = self.usedBy
        return item
