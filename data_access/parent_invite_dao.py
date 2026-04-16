from data_access.base_dao import BaseDAO
from models.parent_invite import ParentInvite
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class ParentInviteDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("parent_invite")

    def create_invite(self, invite: ParentInvite) -> None:
        self.table.put_item(Item=invite.to_item())

    def get_invite_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        response = self.table.query(
            KeyConditionExpression=Key("code").eq(code)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def mark_used(self, code: str) -> None:
        self.table.update_item(
            Key={"code": code},
            UpdateExpression="SET #used = :used",
            ExpressionAttributeValues={":used": True},
            ExpressionAttributeNames={"#used": "used"}
        )
