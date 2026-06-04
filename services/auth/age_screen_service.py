import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from data_access.age_screen_session_dao import AgeScreenSessionDAO
from data_access.auth_rate_limit_dao import AuthRateLimitDAO
from exceptions.auth_error import AuthError
from exceptions.validation_error import ValidationError

AGE_SCREEN_COOKIE = "eq_age_screen"
AGE_SCREEN_TTL_MINUTES = 10


class AgeScreenService:
    def __init__(self, session_dao=None, rate_limit_dao=None) -> None:
        self.session_dao = session_dao or AgeScreenSessionDAO()
        self.rate_limit_dao = rate_limit_dao or AuthRateLimitDAO()

    def create(self, *, birth_month: int, birth_year: int, request_ip: str) -> tuple[str, str]:
        if not self.rate_limit_dao.allow(
            scope="age_screen_ip",
            identifier=request_ip,
            maximum=20,
            window_seconds=15 * 60,
        ):
            raise ValidationError("Too many age-screen attempts. Please try again later.")

        age_band = self._compute_age_band(birth_month=birth_month, birth_year=birth_year)
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=AGE_SCREEN_TTL_MINUTES)
        self.session_dao.create(
            {
                "token_hash": self._hash(raw_token),
                "age_band": age_band,
                "signal_source": "self_screen",
                "expires_at": expires_at.isoformat(),
                "created_at": now.isoformat(),
                "delete_after": (expires_at + timedelta(hours=24)).isoformat(),
            }
        )
        return raw_token, age_band

    def consume(self, raw_token: str | None, *, expected_band: str) -> dict[str, Any]:
        if not raw_token:
            raise AuthError("Complete the age screen before student signup.")
        record = self.session_dao.consume(self._hash(raw_token))
        if not record:
            raise AuthError("The age screen expired or was already used. Please start again.")
        if record.get("age_band") != expected_band:
            raise AuthError("The age-screen result does not match this signup.")
        return record

    @staticmethod
    def _compute_age_band(*, birth_month: int, birth_year: int) -> str:
        now = datetime.now(timezone.utc)
        if birth_month < 1 or birth_month > 12:
            raise ValidationError("Birth month must be between 1 and 12.")
        if birth_year < 1900 or birth_year > now.year:
            raise ValidationError("Birth year is invalid.")

        # Without collecting a birth day, classify conservatively throughout
        # the birth month. A user ages into the next band on the following month.
        age = now.year - birth_year - (1 if birth_month >= now.month else 0)
        if age < 13:
            return "under_13"
        if age < 18:
            return "13_to_17"
        return "18_plus"

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()
