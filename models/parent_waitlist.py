"""Parent waitlist model.

Compliance note: this model intentionally contains **no child PII**.
`num_children` is an aggregate count only — never identifiers, names,
ages, or grades. See supabase/migrations/003_parent_waitlist.sql for
the full compliance rationale.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ParentWaitlistEntry:
    first_name: str
    last_name: str
    email: str
    num_children: int
    learning_challenge: Optional[str] = None
    open_to_interview: bool = False
    contact_method: Optional[str] = None
    source: str = "parent_waitlist"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_row(self) -> Dict[str, Any]:
        """Shape suitable for Supabase insert."""
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "num_children": self.num_children,
            "learning_challenge": self.learning_challenge,
            "open_to_interview": self.open_to_interview,
            "contact_method": self.contact_method,
            "source": self.source,
            "created_at": self.created_at,
        }
