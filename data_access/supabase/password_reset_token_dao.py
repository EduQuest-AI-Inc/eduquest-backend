from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from data_access.supabase.base_dao import SupabaseBaseDAO


class PasswordResetTokenDAO(SupabaseBaseDAO):
    MAX_ATTEMPTS = 5

    def __init__(self):
        super().__init__('password_reset_token')

    def add_token(self, token) -> None:
        self._insert({
            'token_hash': token.token_hash,
            'user_id': token.user_id,
            'role': token.role,
            'email_lc': token.email_lc,
            'created_at': token.created_at_iso if hasattr(token, 'created_at_iso') else token.created_at,
            'expires_at': (
                datetime.fromtimestamp(token.expires_at_epoch, tz=timezone.utc).isoformat()
                if hasattr(token, 'expires_at_epoch')
                else token.expires_at
            ),
            'request_ip': token.request_ip,
            'user_agent': token.user_agent,
            'attempts': getattr(token, 'attempts', 0),
        })

    def get_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('token_hash', token_hash)

    def is_token_valid(self, token_hash: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        token_data = self.get_token(token_hash)
        if not token_data:
            return False, None, 'not_found'

        now = datetime.now(timezone.utc).isoformat()
        if token_data.get('expires_at', '') < now:
            return False, token_data, 'expired'
        if token_data.get('used_at'):
            return False, token_data, 'already_used'
        if token_data.get('burned_at'):
            return False, token_data, 'burned'

        return True, token_data, None

    def increment_attempts(self, token_hash: str) -> bool:
        result = self._rpc('increment_token_attempts', {'p_token_hash': token_hash})
        if result and len(result) > 0:
            return result[0].get('burned_at') is not None
        return False

    def burn_token(self, token_hash: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._update(
            {'token_hash': token_hash},
            {'burned_at': now},
        )

    def consume_token(self, token_hash: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        result = self._rpc('consume_password_reset_token', {'p_token_hash': token_hash})
        if result and len(result) > 0:
            return True, result[0], None

        # Token was not consumed — figure out why
        token_data = self.get_token(token_hash)
        if not token_data:
            return False, None, 'not_found'
        if token_data.get('used_at'):
            return False, token_data, 'already_used'
        if token_data.get('burned_at'):
            return False, token_data, 'burned'

        now = datetime.now(timezone.utc).isoformat()
        if token_data.get('expires_at', '') <= now:
            return False, token_data, 'expired'

        return False, token_data, 'unknown'

    def delete_token(self, token_hash: str) -> None:
        self._delete({'token_hash': token_hash})
