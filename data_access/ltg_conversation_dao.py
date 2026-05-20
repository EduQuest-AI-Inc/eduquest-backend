from typing import Optional
from datetime import datetime, timezone

from data_access.base_dao import SupabaseBaseDAO


class LtgConversationDAO(SupabaseBaseDAO):
    """DAO for the ltg_conversation table.

    Each row maps (user_id, period_id) → conversation_id (OpenAI).
    """

    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('ltg_conversation', jwt=jwt)

    def get_conversation_id(self, user_id: str, period_id: str) -> Optional[str]:
        response = self._execute(
            self._table()
            .select('conversation_id')
            .eq('user_id', user_id)
            .eq('period_id', period_id)
            .maybe_single()
        )
        row = self._row(response)
        return row['conversation_id'] if row else None

    def get_last_response_id(self, user_id: str, period_id: str) -> Optional[str]:
        response = self._execute(
            self._table()
            .select('last_response_id')
            .eq('user_id', user_id)
            .eq('period_id', period_id)
            .maybe_single()
        )
        row = self._row(response)
        return row.get('last_response_id') if row else None

    def update_last_response_id(self, user_id: str, period_id: str, response_id: str) -> None:
        self._update(
            {'user_id': user_id, 'period_id': period_id},
            {'last_response_id': response_id},
        )

    def get_all_for_student(self, user_id: str) -> dict[str, str]:
        """Return {period_id: conversation_id} for a student."""
        rows = self._select_eq('user_id', user_id)
        return {r['period_id']: r['conversation_id'] for r in rows}

    def upsert_conversation(
        self,
        user_id: str,
        period_id: str,
        conversation_id: str,
        last_response_id: Optional[str] = None,
    ) -> None:
        data = {
            'user_id': user_id,
            'period_id': period_id,
            'conversation_id': conversation_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        if last_response_id is not None:
            data['last_response_id'] = last_response_id
        self._upsert(data)

    def delete_conversation(self, user_id: str, period_id: str) -> Optional[str]:
        """Delete the mapping and return the conversation_id that was removed, or None."""
        existing = self.get_conversation_id(user_id, period_id)
        if existing:
            self._delete({'user_id': user_id, 'period_id': period_id})
        return existing

    def find_period_for_conversation(self, user_id: str, conversation_id: str) -> Optional[str]:
        """Find which period_id a conversation_id belongs to for a student."""
        response = self._execute(
            self._table()
            .select('period_id')
            .eq('user_id', user_id)
            .eq('conversation_id', conversation_id)
            .maybe_single()
        )
        row = self._row(response)
        return row['period_id'] if row else None
