from data_access.base_dao import BaseDAO
from models.administrator import Administrator
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class AdminDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("administrator")

    def add_admin(self, admin: Administrator) -> None:
        self.table.put_item(Item=admin.to_item())

    def get_admin_by_id(self, admin_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("admin_id").eq(admin_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def get_admins_by_school(self, school_id: str) -> List[Dict[str, Any]]:
        response = self.table.scan(
            FilterExpression=Key("school_id").eq(school_id)
        )
        return response.get("Items", [])

    def update_admin(self, admin_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"admin_id": admin_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_admin(self, admin_id: str) -> None:
        self.table.delete_item(Key={"admin_id": admin_id})
