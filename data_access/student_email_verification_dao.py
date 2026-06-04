from typing import Any

from data_access.base_dao import SupabaseBaseDAO


class StudentEmailVerificationDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__("student_email_verification")

    def create(self, record: dict[str, Any]) -> None:
        self._insert(record)

    def confirm(
        self,
        *,
        email_hmac: str,
        code_hash: str,
        verified_token_hash: str,
    ) -> dict[str, Any] | None:
        result = self._rpc(
            "confirm_student_email_verification",
            {
                "p_email_hmac": email_hmac,
                "p_code_hash": code_hash,
                "p_verified_token_hash": verified_token_hash,
            },
        )
        if not isinstance(result, list) or not result:
            return None
        return result[0]

    def consume(self, *, email_hmac: str, verified_token_hash: str) -> dict[str, Any] | None:
        result = self._rpc(
            "consume_student_email_verification",
            {
                "p_email_hmac": email_hmac,
                "p_verified_token_hash": verified_token_hash,
            },
        )
        if not isinstance(result, list) or not result:
            return None
        return result[0]
