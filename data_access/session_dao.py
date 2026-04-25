from typing import List, Dict, Any

from data_access.base_dao import SupabaseBaseDAO


class SessionDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('session')

    def add_session(self, session) -> None:
        self._insert({
            'auth_token': session.auth_token,
            'user_id': session.user_id,
            'role': session.role,
            'expires_at': session.expires_at,
        })

    def get_sessions_by_auth_token(self, auth_token: str) -> List[Dict[str, Any]]:
        return self._select_eq('auth_token', auth_token)

    def update_session(self, auth_token: str, updates: Dict[str, Any]) -> None:
        self._update({'auth_token': auth_token}, updates)

    def delete_session(self, auth_token: str) -> None:
        self._delete({'auth_token': auth_token})
