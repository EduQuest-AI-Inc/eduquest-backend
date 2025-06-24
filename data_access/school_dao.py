from data_access.base_dao import BaseDAO
from models.school import School
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class SchoolDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("school")

    def add_school(self, school: School) -> None:
        self.table.put_item(Item=school.to_item())

    def get_school_by_id(self, school_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("school_id").eq(school_id)
        )
        return response["Items"]

    def update_school(self, school_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"school_id": school_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_school(self, school_id: str) -> None:
        self.table.delete_item(Key={"school_id": school_id})
