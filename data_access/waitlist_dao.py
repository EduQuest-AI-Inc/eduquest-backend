from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from models.waitlist import PilotWaitlistEntry
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class WaitlistDAO(BaseDAO):
    """
    Data Access Object for the pilot study waitlist.
    Manages teacher entries in the waitlist for pilot study access.
    
    DynamoDB Key Schema:
    - Partition Key: waitlistID (stores teacher_id)
    - Sort Key: email (stores teacher's email)
    
    Because of the composite key, we use Query instead of GetItem
    when we only know the teacher_id (partition key).
    """

    def __init__(self):
        cfg = DynamoDBConfig()
        self.table = cfg.get_table("waitlist")
        self.referral_code_index = "referralCode-index"

    def get_by_teacher_id(self, teacher_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a waitlist entry by teacher ID.
        Uses Query since we only know the partition key, not the sort key (email).
        Returns the first matching item or None.
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key("waitlistID").eq(teacher_id),
                # Filter for pilot waitlist entries only (have 'status' field)
                FilterExpression=Attr("status").exists(),
                Limit=1
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except ClientError:
            return None

    def get_by_referral_code(self, referral_code: str) -> Optional[Dict[str, Any]]:
        """Get a waitlist entry by referral code"""
        try:
            # Try using GSI first
            response = self.table.query(
                IndexName=self.referral_code_index,
                KeyConditionExpression=Key("referralCode").eq(referral_code.upper()),
                Limit=1
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except ClientError:
            # Fallback to scan if GSI doesn't exist
            try:
                response = self.table.scan(
                    FilterExpression=Attr("referralCode").eq(referral_code.upper())
                )
                items = response.get("Items", [])
                return items[0] if items else None
            except ClientError:
                return None

    def get_waitlist_count(self) -> int:
        """
        Get the total number of pilot waitlist entries.
        Filters for entries that have a 'status' field (pilot entries only).
        """
        try:
            response = self.table.scan(
                FilterExpression=Attr("status").exists(),
                Select="COUNT"
            )
            return response.get("Count", 0)
        except ClientError:
            return 0

    def get_pending_count(self) -> int:
        """Get the number of pending entries (for position calculation)"""
        try:
            response = self.table.scan(
                FilterExpression=Attr("status").eq("pending"),
                Select="COUNT"
            )
            return response.get("Count", 0)
        except ClientError:
            return 0

    def join_waitlist(self, teacher_id: str, teacher_email: str, referred_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a teacher to the pilot study waitlist.
        Returns the created entry or existing entry if already on waitlist.
        
        Args:
            teacher_id: The teacher's username/ID (stored in waitlistID)
            teacher_email: The teacher's email (required - sort key)
            referred_by: Optional teacher ID of who referred them
        """
        # Check if already on waitlist
        existing = self.get_by_teacher_id(teacher_id)
        if existing:
            return existing

        # Calculate position (number of existing pilot entries + 1)
        position = self.get_waitlist_count() + 1

        # Create new entry
        entry = PilotWaitlistEntry(
            teacher_id=teacher_id,
            email=teacher_email,
            position=position,
            referred_by=referred_by,
        )

        try:
            self.table.put_item(
                Item=entry.to_item(),
                # Composite key condition
                ConditionExpression="attribute_not_exists(waitlistID) AND attribute_not_exists(email)"
            )
            return entry.to_item()
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Entry was created concurrently, return existing
                return self.get_by_teacher_id(teacher_id)
            raise

    def approve_teacher(self, teacher_id: str) -> bool:
        """
        Mark a teacher as approved for pilot study access.
        Must first query to get the email (sort key), then update.
        """
        try:
            # First, get the entry to find the email (sort key)
            entry = self.get_by_teacher_id(teacher_id)
            if not entry:
                return False

            # Now update with both keys
            self.table.update_item(
                Key={
                    "waitlistID": teacher_id,
                    "email": entry["email"]
                },
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "approved"},
            )
            return True
        except ClientError:
            return False

    def get_status(self, teacher_id: str) -> Dict[str, Any]:
        """
        Get the waitlist status for a teacher.
        Returns dict with: on_waitlist, position, referral_code, status, approved
        """
        entry = self.get_by_teacher_id(teacher_id)
        
        if not entry:
            return {
                "on_waitlist": False,
                "approved": False,
                "position": None,
                "referral_code": None,
                "status": None,
            }
        
        return {
            "on_waitlist": True,
            "approved": entry.get("status") == "approved",
            "position": entry.get("position"),
            "referral_code": entry.get("referralCode"),
            "status": entry.get("status"),
            "joined_at": entry.get("joinedAt"),
        }

    def validate_referral_code(self, referral_code: str) -> Dict[str, Any]:
        """
        Validate a referral code.
        Returns dict with 'valid' (bool) and 'referrer_id' if valid.
        """
        if not referral_code:
            return {"valid": False, "error": "Referral code is required"}

        entry = self.get_by_referral_code(referral_code)
        
        if not entry:
            return {"valid": False, "error": "Invalid referral code"}

        return {
            "valid": True,
            "referrer_id": entry.get("waitlistID"),  # teacher_id is stored in waitlistID
        }
