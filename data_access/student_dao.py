from typing import List, Dict
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Any
from datetime import datetime, timezone
from models.student import Student

class StudentDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("student")

    def add_student(self, student: Student) -> None:
        self.table.put_item(Item=student.to_item())

    def get_student_by_id(self, student_id: str) -> List[Dict[str, Any]]:
        response = self.table.query(
            KeyConditionExpression=Key("student_id").eq(student_id)
        )
        return response["Items"]

    def update_student(self, student_id: str, updates: Dict[str, Any]) -> None:
        updates["last_login"] = datetime.now(timezone.utc).isoformat()
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"student_id": student_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_student(self, student_id: str) -> None:
        self.table.delete_item(Key={"student_id": student_id})
