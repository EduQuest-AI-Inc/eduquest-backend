from typing import Optional
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class LtgConversationDAO(SupabaseBaseDAO):
    """DAO for the ltg_conversation table.

    Each row maps (student_id, period_id) → conversation_id (OpenAI).
    """

    def __init__(self):
        super().__init__('ltg_conversation')

    def get_conversation_id(self, student_id: str, period_id: str) -> Optional[str]:
        response = (
            self._table()
            .select('conversation_id')
            .eq('student_id', student_id)
            .eq('period_id', period_id)
            .maybe_single()
            .execute()
        )
        if response is not None and response.data:
            return response.data['conversation_id']
        return None

    def get_all_for_student(self, student_id: str) -> dict[str, str]:
        """Return {period_id: conversation_id} for a student."""
        rows = self._select_eq('student_id', student_id)
        return {r['period_id']: r['conversation_id'] for r in rows}

    def upsert_conversation(self, student_id: str, period_id: str, conversation_id: str) -> None:
        self._upsert({
            'student_id': student_id,
            'period_id': period_id,
            'conversation_id': conversation_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
        })

    def delete_conversation(self, student_id: str, period_id: str) -> Optional[str]:
        """Delete the mapping and return the conversation_id that was removed, or None."""
        existing = self.get_conversation_id(student_id, period_id)
        if existing:
            self._delete({'student_id': student_id, 'period_id': period_id})
        return existing

    def find_period_for_conversation(self, student_id: str, conversation_id: str) -> Optional[str]:
        """Find which period_id a conversation_id belongs to for a student."""
        response = (
            self._table()
            .select('period_id')
            .eq('student_id', student_id)
            .eq('conversation_id', conversation_id)
            .maybe_single()
            .execute()
        )
        if response is not None and response.data:
            return response.data['period_id']
        return None
