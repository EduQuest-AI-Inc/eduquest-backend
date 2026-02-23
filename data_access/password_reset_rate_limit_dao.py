"""
DAO for password reset rate limiting.
Uses DynamoDB with TTL for automatic cleanup.
"""

from typing import Tuple
import time

from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


class PasswordResetRateLimitDAO(BaseDAO):
    """
    Rate limiting for password reset requests.
    
    Uses aligned time windows and atomic counters with TTL.
    """
    
    # Rate limit settings
    WINDOW_SIZE_SECONDS = 900  # 15 minutes
    MAX_REQUESTS_PER_IP_EMAIL = 5  # Max requests per (IP + email) per window
    MAX_REQUESTS_PER_IP = 20  # Max requests per IP per window
    COOLDOWN_SECONDS = 300  # 5 minutes cooldown between emails to same address
    
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("password_reset_rate_limit")
    
    def _get_window_start(self) -> int:
        """Get the start of the current aligned window."""
        current_time = int(time.time())
        return (current_time // self.WINDOW_SIZE_SECONDS) * self.WINDOW_SIZE_SECONDS
    
    def _get_ip_email_key(self, ip: str, email_lc: str) -> str:
        """Generate key for IP + email rate limit."""
        window_start = self._get_window_start()
        return f"ip:{ip}|email:{email_lc}|w:{window_start}"
    
    def _get_ip_key(self, ip: str) -> str:
        """Generate key for IP-only rate limit."""
        window_start = self._get_window_start()
        return f"ip:{ip}|w:{window_start}"
    
    def _get_cooldown_key(self, email_lc: str) -> str:
        """Generate key for email cooldown."""
        return f"cooldown:email:{email_lc}"
    
    def check_rate_limit(self, ip: str, email_lc: str) -> Tuple[bool, str]:
        """
        Check if a request is rate-limited.
        
        Returns:
            (is_allowed, reason) - is_allowed is True if request should proceed
        """
        # Check cooldown first (most specific)
        if self._is_on_cooldown(email_lc):
            return False, "cooldown"
        
        # Check IP + email rate limit
        ip_email_count = self._get_count(self._get_ip_email_key(ip, email_lc))
        if ip_email_count >= self.MAX_REQUESTS_PER_IP_EMAIL:
            return False, "ip_email_limit"
        
        # Check IP-only rate limit
        ip_count = self._get_count(self._get_ip_key(ip))
        if ip_count >= self.MAX_REQUESTS_PER_IP:
            return False, "ip_limit"
        
        return True, ""
    
    def record_request(self, ip: str, email_lc: str) -> None:
        """Record a request for rate limiting purposes."""
        # Increment IP + email counter
        self._increment_counter(self._get_ip_email_key(ip, email_lc))
        
        # Increment IP-only counter
        self._increment_counter(self._get_ip_key(ip))
    
    def set_cooldown(self, email_lc: str) -> None:
        """Set a cooldown for an email (after sending a reset email)."""
        key = self._get_cooldown_key(email_lc)
        expires_at = int(time.time()) + self.COOLDOWN_SECONDS
        
        try:
            self.table.put_item(
                Item={
                    "key": key,
                    "count": 1,
                    "expires_at_epoch": expires_at
                },
                ConditionExpression="attribute_not_exists(#k)",
                ExpressionAttributeNames={"#k": "key"}
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # Cooldown already exists, that's fine
                pass
            else:
                raise
    
    def _is_on_cooldown(self, email_lc: str) -> bool:
        """Check if an email is on cooldown."""
        key = self._get_cooldown_key(email_lc)
        try:
            response = self.table.get_item(Key={"key": key})
            item = response.get("Item")
            if not item:
                return False
            
            # Check if cooldown has expired (in case TTL hasn't cleaned it up yet)
            current_time = int(time.time())
            return item.get("expires_at_epoch", 0) > current_time
            
        except ClientError:
            return False
    
    def _get_count(self, key: str) -> int:
        """Get the current count for a rate limit key."""
        try:
            response = self.table.get_item(Key={"key": key})
            item = response.get("Item")
            if not item:
                return 0
            
            # Check if expired (in case TTL hasn't cleaned it up yet)
            current_time = int(time.time())
            if item.get("expires_at_epoch", 0) <= current_time:
                return 0
            
            return item.get("count", 0)
            
        except ClientError:
            return 0
    
    def _increment_counter(self, key: str) -> int:
        """Atomically increment a counter, creating it if needed."""
        # Window expiry: end of current window + buffer
        window_start = self._get_window_start()
        expires_at = window_start + self.WINDOW_SIZE_SECONDS + 60  # 1 minute buffer
        
        try:
            response = self.table.update_item(
                Key={"key": key},
                UpdateExpression="SET #count = if_not_exists(#count, :zero) + :inc, expires_at_epoch = :exp",
                ExpressionAttributeNames={"#count": "count"},
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":inc": 1,
                    ":exp": expires_at
                },
                ReturnValues="UPDATED_NEW"
            )
            return response.get("Attributes", {}).get("count", 1)
            
        except ClientError:
            return 0
    
    def check_confirm_rate_limit(self, ip: str) -> Tuple[bool, str]:
        """
        Check rate limit for confirm endpoint (by IP only).
        Uses a separate counter to avoid interference with request endpoint.
        
        Returns:
            (is_allowed, reason)
        """
        window_start = self._get_window_start()
        key = f"confirm:ip:{ip}|w:{window_start}"
        
        count = self._get_count(key)
        if count >= self.MAX_REQUESTS_PER_IP:
            return False, "ip_limit"
        
        return True, ""
    
    def record_confirm_attempt(self, ip: str) -> None:
        """Record a confirm attempt for rate limiting."""
        window_start = self._get_window_start()
        key = f"confirm:ip:{ip}|w:{window_start}"
        self._increment_counter(key)

