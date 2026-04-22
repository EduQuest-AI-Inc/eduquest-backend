from typing import List, Dict, Any, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class ConversationDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('conversation')

    def add_conversation(self, conversation) -> None:
        self._insert({
            'conversation_id': conversation.conversation_id,
            'user_id': conversation.user_id,
            'role': conversation.role,
            'conversation_type': conversation.conversation_type,
            'period_id': getattr(conversation, 'period_id', None),
            'last_response_id': getattr(conversation, 'last_response_id', None),
            'created_at': getattr(conversation, 'created_at', None),
        })

    def get_conversations_by_id(self, conversation_id: str) -> List[dict]:
        return self._select_eq('conversation_id', conversation_id)

    def update_conversation(self, conversation_id: str, updates: Dict[str, Any]) -> None:
        self._update({'conversation_id': conversation_id}, updates)

    def delete_conversation(self, conversation_id: str) -> None:
        self._delete({'conversation_id': conversation_id})

    def get_conversation_by_id_user_type(
        self, conversation_id: str, user_id: str, conversation_type: str
    ) -> Optional[dict]:
        response = (
            self._table()
            .select('*')
            .eq('conversation_id', conversation_id)
            .eq('user_id', user_id)
            .eq('conversation_type', conversation_type)
            .maybe_single()
            .execute()
        )
        return response.data
