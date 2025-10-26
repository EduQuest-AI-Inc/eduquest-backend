from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig

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

    def put_unique_code(self, waitlist_id: str, email: str, name: str) -> bool:
        try:
            self.table.put_item(
                Item={
                    "waitlistID": waitlist_id,
                    "email": email.strip().lower(),
                    "name": name.strip(),
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
