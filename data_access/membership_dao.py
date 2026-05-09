from typing import Any, Dict, List, Optional

from data_access.base_dao import SupabaseBaseDAO


class MembershipDAO(SupabaseBaseDAO):
    """One row per parent/teacher account. Students never have a row."""

    def __init__(self) -> None:
        super().__init__("membership")

    def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id("user_id", user_id)

    def get_by_stripe_customer_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        rows = self._select_eq("stripe_customer_id", customer_id)
        return rows[0] if rows else None

    def get_by_stripe_subscription_id(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        rows = self._select_eq("stripe_subscription_id", subscription_id)
        return rows[0] if rows else None

    def upsert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._upsert(data)

    def update(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        rows = self._update({"user_id": user_id}, updates)
        return rows[0] if rows else {}

    def delete(self, user_id: str) -> None:
        self._delete({"user_id": user_id})

    def list_trialing_needing_reminder(self, before_iso: str) -> List[Dict[str, Any]]:
        """Return trialing memberships whose trial_ends_at <= before_iso and
        which have not yet had reminder_sent_at populated."""
        response = self._execute(
            self._table()
            .select("*")
            .eq("status", "trialing")
            .is_("reminder_sent_at", None)
            .lte("trial_ends_at", before_iso)
        )
        return self._rows(response.data)

    def list_trialing_expired(self, before_iso: str) -> List[Dict[str, Any]]:
        """Return trialing memberships whose trial has elapsed without conversion."""
        response = self._execute(
            self._table()
            .select("*")
            .eq("status", "trialing")
            .lte("trial_ends_at", before_iso)
        )
        return self._rows(response.data)
