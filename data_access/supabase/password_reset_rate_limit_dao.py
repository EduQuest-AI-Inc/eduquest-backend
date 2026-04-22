from typing import Tuple
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class PasswordResetRateLimitDAO(SupabaseBaseDAO):
    WINDOW_SIZE_SECONDS = 900   # 15 minutes
    MAX_REQUESTS_PER_IP_EMAIL = 5
    MAX_REQUESTS_PER_IP = 20
    COOLDOWN_SECONDS = 300      # 5 minutes

    def __init__(self) -> None:
        super().__init__('password_reset_rate_limit')

    # -- key helpers -----------------------------------------------------------

    def _get_window_start(self) -> int:
        current_time = int(datetime.now(timezone.utc).timestamp())
        return (current_time // self.WINDOW_SIZE_SECONDS) * self.WINDOW_SIZE_SECONDS

    def _get_ip_email_key(self, ip: str, email_lc: str) -> str:
        return f"ip:{ip}|email:{email_lc}|w:{self._get_window_start()}"

    def _get_ip_key(self, ip: str) -> str:
        return f"ip:{ip}|w:{self._get_window_start()}"

    def _get_cooldown_key(self, email_lc: str) -> str:
        return f"cooldown:email:{email_lc}"

    # -- public API (same signatures as DynamoDB version) ----------------------

    def check_rate_limit(self, ip: str, email_lc: str) -> Tuple[bool, str]:
        if self._is_on_cooldown(email_lc):
            return False, 'cooldown'

        ip_email_count = self._get_count(self._get_ip_email_key(ip, email_lc))
        if ip_email_count >= self.MAX_REQUESTS_PER_IP_EMAIL:
            return False, 'ip_email_limit'

        ip_count = self._get_count(self._get_ip_key(ip))
        if ip_count >= self.MAX_REQUESTS_PER_IP:
            return False, 'ip_limit'

        return True, ''

    def record_request(self, ip: str, email_lc: str) -> None:
        self._increment_counter(self._get_ip_email_key(ip, email_lc))
        self._increment_counter(self._get_ip_key(ip))

    def set_cooldown(self, email_lc: str) -> None:
        key = self._get_cooldown_key(email_lc)
        expires_at = datetime.fromtimestamp(
            int(datetime.now(timezone.utc).timestamp()) + self.COOLDOWN_SECONDS,
            tz=timezone.utc,
        ).isoformat()
        self._upsert({'key': key, 'count': 1, 'expires_at': expires_at})

    def check_confirm_rate_limit(self, ip: str) -> Tuple[bool, str]:
        key = f"confirm:ip:{ip}|w:{self._get_window_start()}"
        count = self._get_count(key)
        if count >= self.MAX_REQUESTS_PER_IP:
            return False, 'ip_limit'
        return True, ''

    def record_confirm_attempt(self, ip: str) -> None:
        key = f"confirm:ip:{ip}|w:{self._get_window_start()}"
        self._increment_counter(key)

    # -- internal helpers ------------------------------------------------------

    def _is_on_cooldown(self, email_lc: str) -> bool:
        key = self._get_cooldown_key(email_lc)
        item = self._select_by_id('key', key)
        if not item:
            return False
        now = datetime.now(timezone.utc).isoformat()
        return item.get('expires_at', '') > now

    def _get_count(self, key: str) -> int:
        item = self._select_by_id('key', key)
        if not item:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        if item.get('expires_at', '') <= now:
            return 0
        return item.get('count', 0)

    def _increment_counter(self, key: str) -> int:
        window_seconds = self.WINDOW_SIZE_SECONDS + 60  # 1 minute buffer
        result = self._rpc('increment_rate_limit', {
            'p_key': key,
            'p_window_seconds': window_seconds,
        })
        return result if isinstance(result, int) else 0
