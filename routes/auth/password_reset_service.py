"""
Password reset service for EduQuest.
Handles the business logic for password reset request and confirmation.
"""

import secrets
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from werkzeug.security import generate_password_hash

import os
if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
    from data_access.supabase.student_dao import StudentDAO
    from data_access.supabase.teacher_dao import TeacherDAO
    from data_access.supabase.password_reset_token_dao import PasswordResetTokenDAO
    from data_access.supabase.password_reset_rate_limit_dao import PasswordResetRateLimitDAO
else:
    from data_access.student_dao import StudentDAO
    from data_access.teacher_dao import TeacherDAO
    from data_access.password_reset_token_dao import PasswordResetTokenDAO
    from data_access.password_reset_rate_limit_dao import PasswordResetRateLimitDAO
from models.password_reset_token import PasswordResetToken
from services.email_service import get_email_service
from .password_policy import validate_password

# Configure logging
logger = logging.getLogger(__name__)

# Neutral message for request endpoint (always the same)
NEUTRAL_REQUEST_MESSAGE = "If an account exists with that email, we sent a password reset link."

# Uniform error message for confirm endpoint
INVALID_TOKEN_MESSAGE = "This link is invalid or expired. Please request a new one."


class PasswordResetService:
    """Service for handling password reset operations."""
    
    def __init__(self):
        self.student_dao = StudentDAO()
        self.teacher_dao = TeacherDAO()
        self.token_dao = PasswordResetTokenDAO()
        self.rate_limit_dao = PasswordResetRateLimitDAO()
        self.email_service = get_email_service()
    
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
        email_lc = email.strip().lower() if email else ""
        
        # Log the request
        self._log_event("PASSWORD_RESET_REQUEST_RECEIVED", request_id, email_lc=email_lc, ip=ip_address)
        
        # Check rate limits
        is_allowed, limit_reason = self.rate_limit_dao.check_rate_limit(ip_address, email_lc)
        if not is_allowed:
            self._log_event(
                "PASSWORD_RESET_REQUEST_RATE_LIMITED",
                request_id,
                email_lc=email_lc,
                ip=ip_address,
                result=limit_reason
            )
            # Still return neutral message
            return {"success": True, "message": NEUTRAL_REQUEST_MESSAGE}
        
        # Record the request for rate limiting
        self.rate_limit_dao.record_request(ip_address, email_lc)
        
        # Find user by email
        user_data, role = self._find_user_by_email(email_lc)
        
        if not user_data:
            self._log_event(
                "PASSWORD_RESET_REQUEST_USER_NOT_FOUND",
                request_id,
                email_lc=email_lc,
                ip=ip_address
            )
            # Still return neutral message
            return {"success": True, "message": NEUTRAL_REQUEST_MESSAGE}
        
        user_id = user_data.get("student_id") or user_data.get("teacher_id")
        first_name = user_data.get("first_name")
        
        try:
            # Generate token
            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            
            # Create token record
            token_record = PasswordResetToken(
                token_hash=token_hash,
                user_id=user_id,
                role=role,
                email_lc=email_lc,
                created_at_iso=datetime.now(timezone.utc).isoformat(),
                request_ip=ip_address,
                user_agent=user_agent
            )
            
            # Store token
            self.token_dao.add_token(token_record)
            
            self._log_event(
                "PASSWORD_RESET_TOKEN_CREATED",
                request_id,
                email_lc=email_lc,
                user_id=user_id,
                role=role,
                ip=ip_address,
                token_hash_prefix=token_hash[:8]
            )
            
            # Send email
            email_result = self.email_service.send_password_reset_email(
                to_email=email_lc,
                reset_token=raw_token,
                user_first_name=first_name
            )
            
            if email_result.get("success"):
                # Set cooldown after successful send
                self.rate_limit_dao.set_cooldown(email_lc)
                
                self._log_event(
                    "PASSWORD_RESET_EMAIL_SENT",
                    request_id,
                    email_lc=email_lc,
                    user_id=user_id,
                    role=role,
                    ip=ip_address,
                    ses_message_id=email_result.get("message_id")
                )
            else:
                self._log_event(
                    "PASSWORD_RESET_EMAIL_FAILED",
                    request_id,
                    email_lc=email_lc,
                    user_id=user_id,
                    role=role,
                    ip=ip_address,
                    result=email_result.get("error")
                )
            
        except Exception as e:
            self._log_event(
                "PASSWORD_RESET_REQUEST_ERROR",
                request_id,
                email_lc=email_lc,
                ip=ip_address,
                result=str(e)
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
        user_id = consumed_token_data.get("user_id")
        role = consumed_token_data.get("role")
        email_lc = consumed_token_data.get("email_lc")
        
        try:
            hashed_password = generate_password_hash(new_password)
            
            if role == "teacher":
                self.teacher_dao.update_teacher(user_id, {"password": hashed_password})
            else:
                self.student_dao.update_student(user_id, {"password": hashed_password})
            
            self._log_event(
                "PASSWORD_RESET_SUCCESS",
                request_id,
                email_lc=email_lc,
                user_id=user_id,
                role=role,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix
            )
            
            return True, "Your password has been updated successfully. You can now log in with your new password."
            
        except Exception as e:
            # Password update failed after consuming token
            self._log_event(
                "PASSWORD_RESET_UPDATE_FAILED",
                request_id,
                email_lc=email_lc,
                user_id=user_id,
                role=role,
                ip=ip_address,
                token_hash_prefix=token_hash_prefix,
                result=str(e)
            )
            logger.exception(f"Failed to update password after consuming token: {e}")
            
            # Return generic error - user will need to request a new link
            return False, "An error occurred while updating your password. Please request a new reset link."
    
    def _find_user_by_email(self, email_lc: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        Find a user by their canonical email address.
        
        Returns:
            (user_data, role) or (None, None) if not found
        """
        # Check students first
        if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
            student_items = self.student_dao.get_student_by_email_lc(email_lc)
        else:
            student_items = self.student_dao.table.scan(
                FilterExpression="email_lc = :email_lc",
                ExpressionAttributeValues={":email_lc": email_lc}
            ).get("Items", [])

        if student_items:
            return student_items[0] if isinstance(student_items, list) else student_items, "student"

        # Check teachers
        if os.getenv('USE_SUPABASE', 'false').lower() == 'true':
            teacher_items = self.teacher_dao.get_teacher_by_email_lc(email_lc)
        else:
            teacher_items = self.teacher_dao.table.scan(
                FilterExpression="email_lc = :email_lc",
                ExpressionAttributeValues={":email_lc": email_lc}
            ).get("Items", [])

        if teacher_items:
            return teacher_items[0] if isinstance(teacher_items, list) else teacher_items, "teacher"

        return None, None
    
    def _log_event(
        self,
        event_type: str,
        request_id: str,
        email_lc: Optional[str] = None,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        token_hash_prefix: Optional[str] = None,
        ses_message_id: Optional[str] = None,
        result: Optional[str] = None
    ):
        """Log a password reset event with structured data."""
        log_data = {
            "event_type": event_type,
            "request_id": request_id,
        }
        
        if email_lc:
            log_data["email_lc"] = email_lc
        if user_id:
            log_data["user_id"] = user_id
        if role:
            log_data["role"] = role
        if ip:
            log_data["ip"] = ip
        if user_agent:
            log_data["user_agent"] = user_agent[:100] if user_agent else None
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

