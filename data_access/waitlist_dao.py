from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from data_access.base_dao import SupabaseBaseDAO


class WaitlistDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('waitlist')

    def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('user_id', user_id)

    def get_by_referral_code(self, referral_code: str) -> Optional[Dict[str, Any]]:
        return self._select_by_id('referral_code', referral_code.upper())

    def get_waitlist_count(self) -> int:
        response = self._table().select('*', count='exact').execute()
        return response.count or 0

    def join_waitlist(self, user_id: str, email: str, referred_by: Optional[str] = None) -> Dict[str, Any]:
        existing = self.get_by_user_id(user_id)
        if existing:
            return existing

        position = self.get_waitlist_count() + 1
        referral_code = uuid.uuid4().hex[:8].upper()

        data = {
            'user_id': user_id,
            'email': email,
            'position': position,
            'referral_code': referral_code,
            'referred_by': referred_by,
            'status': 'pending',
            'joined_at': datetime.now(timezone.utc).isoformat(),
        }
        self._insert(data)
        return data

    def approve_user(self, user_id: str) -> bool:
        result = self._update({'user_id': user_id}, {'status': 'approved'})
        return len(result) > 0

    def get_status(self, user_id: str) -> Dict[str, Any]:
        entry = self.get_by_user_id(user_id)
        if not entry:
            return {
                'on_waitlist': False,
                'approved': False,
                'position': None,
                'referral_code': None,
                'status': None,
            }
        return {
            'on_waitlist': True,
            'approved': entry.get('status') == 'approved',
            'position': entry.get('position'),
            'referral_code': entry.get('referral_code'),
            'status': entry.get('status'),
            'joined_at': entry.get('joined_at'),
        }

    def validate_referral_code(self, referral_code: str) -> Dict[str, Any]:
        if not referral_code:
            return {'valid': False, 'error': 'Referral code is required'}
        entry = self.get_by_referral_code(referral_code)
        if not entry:
            return {'valid': False, 'error': 'Invalid referral code'}
        return {
            'valid': True,
            'referrer_id': entry.get('user_id'),
        }
