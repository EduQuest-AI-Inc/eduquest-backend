from typing import Dict, Any, Optional

from data_access.base_dao import SupabaseBaseDAO


class ParentInviteDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('parent_invite')

    def create_invite(self, invite) -> None:
        self._insert(invite.to_item())

    def get_invite_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        rows = self._select_eq('code', code)
        return rows[0] if rows else None

    def mark_used(self, code: str) -> None:
        self._update({'code': code}, {'used': True})
