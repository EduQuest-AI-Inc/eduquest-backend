import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from data_access.age_screen_session_dao import AgeScreenSessionDAO
from data_access.auth_rate_limit_dao import AuthRateLimitDAO
from data_access.student_email_verification_dao import StudentEmailVerificationDAO
from exceptions.auth_error import AuthError
from exceptions.validation_error import ValidationError
from integrations.email_service import get_email_service
from services.auth.age_screen_service import _sha256_hex

STUDENT_EMAIL_COOKIE = "eq_student_email_verified"
STUDENT_EMAIL_TTL_MINUTES = 10


class StudentEmailVerificationService:
    def __init__(
        self,
        *,
        verification_dao=None,
        age_screen_dao=None,
        rate_limit_dao=None,
        email_service=None,
        secret: str | None = None,
    ) -> None:
        self.verification_dao = verification_dao or StudentEmailVerificationDAO()
        self.age_screen_dao = age_screen_dao or AgeScreenSessionDAO()
        self.rate_limit_dao = rate_limit_dao or AuthRateLimitDAO()
        self.email_service = email_service or get_email_service()
        configured_secret = secret or os.getenv("AUTH_RATE_LIMIT_SECRET") or os.getenv("JWT_SECRET_KEY")
        if not configured_secret:
            raise RuntimeError("AUTH_RATE_LIMIT_SECRET or JWT_SECRET_KEY must be configured")
        self._secret = configured_secret.encode()

    def request_code(self, *, email: str, age_screen_token: str | None, request_ip: str) -> None:
        normalized_email = self._normalize_email(email)
        self._require_adult_age_screen(age_screen_token)
        if not self.rate_limit_dao.allow(
            scope="student_email_request_ip",
            identifier=request_ip,
            maximum=10,
            window_seconds=60 * 60,
        ) or not self.rate_limit_dao.allow(
            scope="student_email_request_email",
            identifier=normalized_email,
            maximum=3,
            window_seconds=60 * 60,
        ):
            raise ValidationError("Too many verification requests. Please try again later.")

        code = f"{secrets.randbelow(1_000_000):06d}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=STUDENT_EMAIL_TTL_MINUTES)
        email_hmac = self._hmac(normalized_email)
        self.verification_dao.create(
            {
                "email_hmac": email_hmac,
                "code_hash": self._hmac(f"{email_hmac}:{code}"),
                "expires_at": expires_at.isoformat(),
                "created_at": now.isoformat(),
                "delete_after": (expires_at + timedelta(hours=24)).isoformat(),
            }
        )
        result = self.email_service.send_student_email_verification_code(
            to_email=normalized_email,
            code=code,
        )
        if not result.get("success"):
            raise ValidationError("Unable to send a verification code. Please try again later.")

    def confirm_code(self, *, email: str, code: str, request_ip: str) -> str:
        normalized_email = self._normalize_email(email)
        if not self.rate_limit_dao.allow(
            scope="student_email_confirm_ip",
            identifier=request_ip,
            maximum=10,
            window_seconds=15 * 60,
        ):
            raise ValidationError("Too many verification attempts. Please try again later.")
        if len(code) != 6 or not code.isdigit():
            raise ValidationError("The verification code is invalid or expired.")

        email_hmac = self._hmac(normalized_email)
        raw_token = secrets.token_urlsafe(32)
        record = self.verification_dao.confirm(
            email_hmac=email_hmac,
            code_hash=self._hmac(f"{email_hmac}:{code}"),
            verified_token_hash=self._sha256(raw_token),
        )
        if not record:
            raise ValidationError("The verification code is invalid or expired.")
        return raw_token

    def consume(self, *, email: str, raw_token: str | None) -> None:
        if not raw_token:
            raise AuthError("Verify your email before student signup.")
        record = self.verification_dao.consume(
            email_hmac=self._hmac(self._normalize_email(email)),
            verified_token_hash=self._sha256(raw_token),
        )
        if not record:
            raise AuthError("The email verification expired or was already used. Please verify again.")

    def _require_adult_age_screen(self, raw_token: str | None) -> None:
        if not raw_token:
            raise AuthError("Complete the age screen before verifying your email.")
        record = self.age_screen_dao.get_valid(_sha256_hex(raw_token))
        if not record or record.get("age_band") != "18_plus":
            raise AuthError("Email verification is available only after an adult age screen.")

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValidationError("Enter a valid email address.")
        return normalized

    def _hmac(self, value: str) -> str:
        return hmac.new(self._secret, value.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()
