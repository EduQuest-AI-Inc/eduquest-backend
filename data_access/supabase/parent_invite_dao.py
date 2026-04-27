from typing import Dict, Any, Optional

from data_access.supabase.base_dao import SupabaseBaseDAO


class ParentInviteDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('parent_invite')

    def create_invite(self, invite) -> None:
        self._insert({
            'code': invite.code,
            'user_id': invite.user_id,
            'expires_at': invite.expires_at,
            'used': invite.used,
        })

    def get_invite_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('code', code)

    def mark_used(self, code: str) -> None:
        self._update({'code': code}, {'used': True})
