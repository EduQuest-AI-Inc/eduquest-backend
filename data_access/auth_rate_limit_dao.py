import hashlib
import hmac
import os

from data_access.base_dao import SupabaseBaseDAO


class AuthRateLimitDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__("auth_rate_limit")
        secret = os.getenv("AUTH_RATE_LIMIT_SECRET") or os.getenv("JWT_SECRET_KEY")
        if not secret:
            raise RuntimeError("AUTH_RATE_LIMIT_SECRET or JWT_SECRET_KEY must be configured")
        self._secret = secret.encode()

    def allow(self, *, scope: str, identifier: str, maximum: int, window_seconds: int) -> bool:
        key_hash = hmac.new(
            self._secret,
            identifier.encode(),
            hashlib.sha256,
        ).hexdigest()
        result = self._rpc(
            "increment_auth_rate_limit",
            {
                "p_scope": scope,
                "p_key_hash": key_hash,
                "p_window_seconds": window_seconds,
            },
        )
        return isinstance(result, int) and result <= maximum
