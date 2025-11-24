from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from datetime import datetime, timezone

class WaitlistDAO(BaseDAO):
    def __init__(self):
        cfg = DynamoDBConfig()
        self.table = cfg.get_table("waitlist")
        self.email_index = "email-index"

    def get_by_email(self, email: str):
        email = email.strip().lower()
        return (self.table.query(
            IndexName=self.email_index,
            KeyConditionExpression=Key("email").eq(email),
            Limit=1
        ).get("Items") or [None])[0]

    def get_by_code(self, waitlist_code: str):
        """Get a waitlist entry by its code (waitlistID)"""
        try:
            scan_response = self.table.scan()
            all_items = scan_response.get('Items', [])
            for item in all_items:
                if item.get('waitlistID') == waitlist_code:
                    return item
            return None
        except ClientError:
            return None

    def validate_code(self, waitlist_code: str) -> dict:
        """
        Validate a waitlist code.
        Returns a dict with 'valid' (bool) and 'error' (str) if invalid
        """
        if not waitlist_code:
            return {"valid": False, "error": "Waitlist code is required"}

        entry = self.get_by_code(waitlist_code)

        if not entry:
            return {"valid": False, "error": "Invalid waitlist code"}

        if entry.get("used", False):
            return {"valid": False, "error": "Waitlist code has already been used"}

        return {"valid": True, "entry": entry}

    def mark_code_as_used(self, waitlist_code: str, used_by: str) -> bool:
        """Mark a waitlist code as used"""
        try:
            self.table.update_item(
                Key={"waitlistID": waitlist_code},
                UpdateExpression="SET #used = :used, usedAt = :usedAt, usedBy = :usedBy",
                ExpressionAttributeNames={"#used": "used"},
                ExpressionAttributeValues={
                    ":used": True,
                    ":usedAt": datetime.now(timezone.utc).isoformat(),
                    ":usedBy": used_by,
                },
            )
            return True
        except ClientError:
            return False

    def put_unique_code(self, waitlist_id: str, email: str, name: str) -> bool:
        try:
            self.table.put_item(
                Item={
                    "waitlistID": waitlist_id,
                    "email": email.strip().lower(),
                    "name": name.strip(),
                    "used": False,
                },
                ConditionExpression="attribute_not_exists(waitlistID)"
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def update_name_if_missing(self, waitlist_id: str, name: str) -> None:
        self.table.update_item(
            Key={"waitlistID": waitlist_id},
            UpdateExpression="SET #n = if_not_exists(#n, :name)",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":name": name.strip()},
        )
