from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

@dataclass
class Waitlist:
    email: str
    waitlistID: str = field(default_factory=lambda: str(uuid.uuid4()))
    createdAt: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_item(self) -> Dict[str, Any]:
        return {
            "waitlistID": self.waitlistID,
            "email": self.email.strip().lower(),
            "createdAt": self.createdAt,
        }
