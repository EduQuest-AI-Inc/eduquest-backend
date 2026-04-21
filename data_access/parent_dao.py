from data_access.base_dao import BaseDAO
from models.parent import Parent
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


class ParentDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("parent")

    def add_parent(self, parent: Parent) -> None:
        self.table.put_item(Item=parent.to_item())

    def get_parent_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        response = self.table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def update_parent(self, user_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}
        self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def delete_parent(self, user_id: str) -> None:
        self.table.delete_item(Key={"user_id": user_id})
