from typing import TYPE_CHECKING, Dict, Any, Optional

from data_access.base_dao import SupabaseBaseDAO

if TYPE_CHECKING:
    from models.user import User

SHARED_USER_FIELDS = {
    "first_name", "last_name", "email", "password", "last_login", "phone_number",
}


class UserDAO(SupabaseBaseDAO):
    def __init__(self, jwt: str | None = None) -> None:
        super().__init__('user', jwt=jwt)

    def add_user(self, user: "User") -> None:
        self._insert(user.model_dump())

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('user_id', user_id)

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        rows = self._select_eq('email', email)
        return rows[0] if rows else None

    def update(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        result = self._update({'user_id': user_id}, updates)
        return result[0] if result else {}

    def delete(self, user_id: str) -> None:
        self._delete({'user_id': user_id})
