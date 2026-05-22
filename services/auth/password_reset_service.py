"""
Password reset service for EduQuest.
Handles the business logic for password reset request and confirmation.
"""

import secrets
import hashlib
import logging
import uuid
from typing import Optional, Tuple

from services.auth.auth_service import generate_password_hash
from services.auth.supabase_auth_service import SupabaseAuthService

from data_access.user_dao import UserDAO
from data_access.password_reset_token_dao import PasswordResetTokenDAO
from data_access.password_reset_rate_limit_dao import PasswordResetRateLimitDAO
from models.password_reset_token import PasswordResetToken
from integrations.email_service import get_email_service
from .password_policy import validate_password

# Configure logging
logger = logging.getLogger(__name__)

# Neutral message for request endpoint (always the same)
NEUTRAL_REQUEST_MESSAGE = "If an account exists with that email, we sent a password reset link."

# Uniform error message for confirm endpoint
INVALID_TOKEN_MESSAGE = "This link is invalid or expired. Please request a new one."


class PasswordResetService:
    """Service for handling password reset operations."""
    
    def __init__(self, supabase_auth_service=None) -> None:
        self.user_dao = UserDAO()
        self.token_dao = PasswordResetTokenDAO()
        self.rate_limit_dao = PasswordResetRateLimitDAO()
        self.email_service = get_email_service()
        self.supabase_auth_service = supabase_auth_service or SupabaseAuthService()
    
    def request_password_reset(
        self,
        email: str,
        ip_address: str,
        user_agent: Optional[str] = None
    ) -> dict:
        """
        Handle a password reset request.
        
        Always returns success with a neutral message to prevent email enumeration.
        
        Args:
            email: The email address provided by the user
            ip_address: The IP address of the requester
            user_agent: The User-Agent header from the request
        
        Returns:
            dict with 'success' (always True) and 'message' (always neutral)
        """
        request_id = str(uuid.uuid4())[:8]
        normalized_email = email.strip().lower() if email else ""

        self._log_event("PASSWORD_RESET_REQUEST_RECEIVED", request_id, email=normalized_email, ip=ip_address)

        is_allowed, limit_reason = self.rate_limit_dao.check_rate_limit(ip_address, normalized_email)
        if not is_allowed:
            self._log_event(
                "PASSWORD_RESET_REQUEST_RATE_LIMITED",
                request_id,
                email=normalized_email,
                ip=ip_address,
                result=limit_reason,
            )
            return {"success": True, "message": NEUTRAL_REQUEST_MESSAGE}

        self.rate_limit_dao.record_request(ip_address, normalized_email)

        user_data, role = self._find_user_by_email(normalized_email)

        if not user_data:
            self._log_event(
                "PASSWORD_RESET_REQUEST_USER_NOT_FOUND",
                request_id,
                email=normalized_email,
                ip=ip_address,
            )
            return {"success": True, "message": NEUTRAL_REQUEST_MESSAGE}

        user_id: Optional[str] = user_data.get("user_id")
        first_name = user_data.get("first_name")
        if not user_id:
            return {"success": True, "message": NEUTRAL_REQUEST_MESSAGE}

        try:
            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            token_record = PasswordResetToken(
                token_hash=token_hash,
                user_id=user_id,
                email=normalized_email,
                request_ip=ip_address,
                user_agent=user_agent,
            )

            self.token_dao.add_token(token_record)

            self._log_event(
                "PASSWORD_RESET_TOKEN_CREATED",
                request_id,
                email=normalized_email,
                user_id=user_id,
                ip=ip_address,
                token_hash_prefix=token_hash[:8],
            )

            email_result = self.email_service.send_password_reset_email(
                to_email=normalized_email,
                reset_token=raw_token,
                user_first_name=first_name,
            )

            if email_result.get("success"):
                self.rate_limit_dao.set_cooldown(normalized_email)
                self._log_event(
                    "PASSWORD_RESET_EMAIL_SENT",
                    request_id,
                    email=normalized_email,
                    user_id=user_id,
                    ip=ip_address,
                    ses_message_id=email_result.get("message_id"),
                )
            else:
                self._log_event(
                    "PASSWORD_RESET_EMAIL_FAILED",
                    request_id,
                    email=normalized_email,
                    user_id=user_id,
                    ip=ip_address,
                    result=email_result.get("error"),
                )

        except Exception as e:
            self._log_event(
                "PASSWORD_RESET_REQUEST_ERROR",
                request_id,
                email=normalized_email,
                ip=ip_address,
                result=str(e),
            )
            logger.exception(f"Error processing password reset request: {e}")
        
        # Always return neutral message
        return {"success": True, "message": NEUTRAL_REQUEST_MESSAGE}
    
    def confirm_password_reset(
        self,
        token: str,
        new_password: str,
        ip_address: str
    ) -> Tuple[bool, str]:
        """
        Confirm a password reset and update the user's password.
        
        Args:
            token: The raw reset token from the URL
            new_password: The new password chosen by the user
            ip_address: The IP address of the requester
        
        Returns:
            (success, message)
        """
        request_id = str(uuid.uuid4())[:8]
        token_hash = hashlib.sha256(token.encode()).hexdigest() if token else ""
        token_hash_prefix = token_hash[:8] if token_hash else "none"
        
        # Check IP rate limit for confirm endpoint
        is_allowed, _ = self.rate_limit_dao.check_confirm_rate_limit(ip_address)
        if not is_allowed:
            self._log_event(
                "PASSWORD_RESET_CONFIRM_RATE_LIMITED",
                request_id,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix
            )
            return False, INVALID_TOKEN_MESSAGE
        
        # Record the confirm attempt
        self.rate_limit_dao.record_confirm_attempt(ip_address)
        
        if not token:
            self._log_event(
                "PASSWORD_RESET_CONFIRM_NO_TOKEN",
                request_id,
                ip=ip_address
            )
            return False, INVALID_TOKEN_MESSAGE
        
        # Validate password before consuming token
        is_valid_pw, pw_error = validate_password(new_password)
        if not is_valid_pw:
            self._log_event(
                "PASSWORD_RESET_CONFIRM_INVALID_PASSWORD",
                request_id,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix
            )
            # Return the password error (this is user-friendly feedback, not security info)
            return False, pw_error
        
        # Check if token exists and is valid (for attempt tracking)
        is_valid, token_data, error_reason = self.token_dao.is_token_valid(token_hash)
        
        if not is_valid:
            # If token exists but is invalid, increment attempts
            if token_data and error_reason not in ("already_used", "burned"):
                was_burned = self.token_dao.increment_attempts(token_hash)
                if was_burned:
                    self._log_event(
                        "PASSWORD_RESET_TOKEN_BURNED",
                        request_id,
                        ip=ip_address,
                        token_hash_prefix=token_hash_prefix
                    )
            
            self._log_event(
                "PASSWORD_RESET_CONFIRM_INVALID",
                request_id,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix,
                result=error_reason or "not_found"
            )
            return False, INVALID_TOKEN_MESSAGE
        
        # Atomically consume the token
        consume_success, consumed_token_data, consume_error = self.token_dao.consume_token(token_hash)
        
        if not consume_success:
            self._log_event(
                "PASSWORD_RESET_CONSUME_FAILED",
                request_id,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix,
                result=consume_error
            )
            return False, INVALID_TOKEN_MESSAGE
        
        # Token consumed successfully, now update password
        if consumed_token_data is None:
            return False, INVALID_TOKEN_MESSAGE
        user_id: Optional[str] = consumed_token_data.get("user_id")
        email: Optional[str] = consumed_token_data.get("email")
        if not user_id:
            return False, INVALID_TOKEN_MESSAGE

        try:
            hashed_password = generate_password_hash(new_password)
            self.user_dao.update(user_id, {"password": hashed_password})

            try:
                user = self.user_dao.get_by_id(user_id)
                if user and user.get("supabase_auth_id"):
                    self.supabase_auth_service.sync_password(user["supabase_auth_id"], new_password)
            except Exception as exc:  # must not block password reset
                logger.warning("Supabase password sync failed for %s: %s", user_id, exc)

            self._log_event(
                "PASSWORD_RESET_SUCCESS",
                request_id,
                email=email,
                user_id=user_id,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix,
            )

            return True, "Your password has been updated successfully. You can now log in with your new password."

        except Exception as e:
            self._log_event(
                "PASSWORD_RESET_UPDATE_FAILED",
                request_id,
                email=email,
                user_id=user_id,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix,
                result=str(e),
            )
            logger.exception(f"Failed to update password after consuming token: {e}")
            return False, "An error occurred while updating your password. Please request a new reset link."

    def _find_user_by_email(self, email: str) -> Tuple[Optional[dict], Optional[str]]:
        """Find a user by their canonical email address. Returns (user_data, role) or (None, None)."""
        user = self.user_dao.get_by_email(email)
        if not user:
            return None, None
        return user, user.get('role')

    def _log_event(
        self,
        event_type: str,
        request_id: str,
        email: Optional[str] = None,
        user_id: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        token_hash_prefix: Optional[str] = None,
        ses_message_id: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        log_data: dict = {"event_type": event_type, "request_id": request_id}
        if email:
            log_data["email"] = email
        if user_id:
            log_data["user_id"] = user_id
        if ip:
            log_data["ip"] = ip
        if user_agent:
            log_data["user_agent"] = user_agent[:100]
        if token_hash_prefix:
            log_data["token_hash_prefix"] = token_hash_prefix
        if ses_message_id:
            log_data["ses_message_id"] = ses_message_id
        if result:
            log_data["result"] = result
        logger.info(f"PasswordReset: {log_data}")


# Singleton instance
_password_reset_service = None


def get_password_reset_service() -> PasswordResetService:
    """Get the singleton password reset service instance."""
    global _password_reset_service
    if _password_reset_service is None:
        _password_reset_service = PasswordResetService()
    return _password_reset_service

