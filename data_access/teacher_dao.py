from data_access.base_dao import BaseDAO
from models.teacher import Teacher
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class TeacherDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("teacher")

    def add_teacher(self, teacher: Teacher) -> None:
        self.table.put_item(Item=teacher.to_item())

    def get_teacher_by_id(self, teacher_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("teacher_id").eq(teacher_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def update_teacher(self, teacher_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"teacher_id": teacher_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_teacher(self, teacher_id: str) -> None:
        self.table.delete_item(Key={"teacher_id": teacher_id})

    # TODO: create GSI for school_id
    def get_teachers_by_school_id(self, school_id: str) -> List[Dict[str, Any]]:
        response = self.table.query(
            IndexName="school_id-index",  # Use GSI
            KeyConditionExpression=Key("school_id").eq(school_id)
        )
        return response.get("Items", [])
