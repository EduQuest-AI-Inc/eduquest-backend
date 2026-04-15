"""Parent waitlist DAO (Supabase-only).

This feature is Supabase-only by design. The pilot-waitlist DAO has
a DynamoDB counterpart for legacy reasons; parent_waitlist is new
and `USE_SUPABASE=true` in production, so we avoid a dead DynamoDB
code path.
"""

from typing import Any, Dict, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class ParentWaitlistDAO(SupabaseBaseDAO):
    def __init__(self):
        super().__init__("parent_waitlist")

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Case-insensitive lookup by email.

        Matches the unique index `idx_parent_waitlist_email_lower`.
        """
        normalized = (email or "").strip().lower()
        if not normalized:
            return None
        rows = (
            self._table()
            .select("*")
            .ilike("email", normalized)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def create(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert(row)
