"""
DAO for password reset token operations.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
import time

from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from models.password_reset_token import PasswordResetToken
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


class PasswordResetTokenDAO(BaseDAO):
    """Data access object for password_reset_token table."""
    
    # Max attempts before token is burned
    MAX_ATTEMPTS = 5
    
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("password_reset_token")
    
    def add_token(self, token: PasswordResetToken) -> None:
        """Store a new password reset token."""
        self.table.put_item(Item=token.to_item())
    
    def get_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get a token by its hash."""
        response = self.table.get_item(Key={"token_hash": token_hash})
        return response.get("Item")
    
    def is_token_valid(self, token_hash: str) -> tuple:
        """
        Check if a token is valid (exists, not expired, not used, not burned).
        
        Returns:
            (is_valid, token_data, error_reason)
        """
        token_data = self.get_token(token_hash)
        
        if not token_data:
            return False, None, "not_found"
        
        current_time = int(time.time())
        
        if token_data.get("expires_at_epoch", 0) < current_time:
            return False, token_data, "expired"
        
        if token_data.get("used_at_iso"):
            return False, token_data, "already_used"
        
        if token_data.get("burned_at_iso"):
            return False, token_data, "burned"
        
        return True, token_data, None
    
    def increment_attempts(self, token_hash: str) -> bool:
        """
        Increment the attempt counter for a token.
        Burns the token if max attempts exceeded.
        
        Returns:
            True if token was burned, False otherwise
        """
        try:
            # Atomically increment attempts
            response = self.table.update_item(
                Key={"token_hash": token_hash},
                UpdateExpression="SET attempts = if_not_exists(attempts, :zero) + :inc",
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":inc": 1
                },
                ReturnValues="UPDATED_NEW"
            )
            
            new_attempts = response.get("Attributes", {}).get("attempts", 0)
            
            # Burn token if max attempts exceeded
            if new_attempts >= self.MAX_ATTEMPTS:
                self.burn_token(token_hash)
                return True
            
            return False
            
        except ClientError:
            return False
    
    def burn_token(self, token_hash: str) -> None:
        """Mark a token as burned (invalidated due to too many attempts)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        # Also set expires_at_epoch to a short time from now for faster cleanup
        soon_epoch = int(time.time()) + 300  # 5 minutes
        
        self.table.update_item(
            Key={"token_hash": token_hash},
            UpdateExpression="SET burned_at_iso = :burned, expires_at_epoch = :exp",
            ExpressionAttributeValues={
                ":burned": now_iso,
                ":exp": soon_epoch
            }
        )
    
    def consume_token(self, token_hash: str) -> tuple:
        """
        Atomically consume a token (mark as used) if it's valid.
        
        Uses a conditional update to ensure the token:
        - Is not already used
        - Is not burned
        - Has not expired
        
        Returns:
            (success, token_data, error_reason)
        """
        current_time = int(time.time())
        now_iso = datetime.now(timezone.utc).isoformat()
        # Set expires_at to soon for faster cleanup after use
        soon_epoch = int(time.time()) + 300  # 5 minutes
        
        try:
            response = self.table.update_item(
                Key={"token_hash": token_hash},
                UpdateExpression="SET used_at_iso = :used, expires_at_epoch = :exp",
                ConditionExpression=(
                    "attribute_not_exists(used_at_iso) AND "
                    "attribute_not_exists(burned_at_iso) AND "
                    "expires_at_epoch > :now"
                ),
                ExpressionAttributeValues={
                    ":used": now_iso,
                    ":exp": soon_epoch,
                    ":now": current_time
                },
                ReturnValues="ALL_NEW"
            )
            return True, response.get("Attributes"), None
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            
            if error_code == "ConditionalCheckFailedException":
                # Token was invalid, check why
                token_data = self.get_token(token_hash)
                if not token_data:
                    return False, None, "not_found"
                if token_data.get("used_at_iso"):
                    return False, token_data, "already_used"
                if token_data.get("burned_at_iso"):
                    return False, token_data, "burned"
                if token_data.get("expires_at_epoch", 0) <= current_time:
                    return False, token_data, "expired"
                return False, token_data, "unknown"
            
            raise
    
    def delete_token(self, token_hash: str) -> None:
        """Delete a token (typically handled by TTL, but available if needed)."""
        self.table.delete_item(Key={"token_hash": token_hash})

