import logging
from typing import List, Dict, Any, Optional
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone
from models.student import Student
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class StudentDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("student")

    def add_student(self, student: Student) -> None:
        self.table.put_item(Item=student.to_item())

    def get_student_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        response = self.table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def update_student(self, user_id: str, updates: Dict[str, Any]) -> None:
        updates["last_login"] = datetime.now(timezone.utc).isoformat()
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}
        self.table.update_item(
            Key={"user_id": str(user_id)},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def delete_student(self, user_id: str) -> None:
        self.table.delete_item(Key={"user_id": user_id})

    def update_long_term_goal(self, user_id: str, period: str, goal: str) -> None:
        student_data = self.get_student_by_id(user_id)
        if not student_data:
            raise ValueError(f"Student with ID {user_id} not found")

        current_goals = student_data.get('long_term_goal', {})
        if isinstance(current_goals, list):
            current_goals = {}

        current_goals[period] = goal
        self.update_student(user_id, {'long_term_goal': current_goals})

    def update_tutorial_status(self, user_id: str, completed_tutorial: bool) -> None:
        if not user_id:
            raise ValueError("Student ID cannot be empty")
        if not isinstance(completed_tutorial, bool):
            raise ValueError("completed_tutorial must be a boolean value")

        existing_student = self.get_student_by_id(user_id)
        if not existing_student:
            raise ValueError(f"Student with ID {user_id} not found")

        self.table.update_item(
            Key={"user_id": str(user_id)},
            UpdateExpression="SET #completed_tutorial = :completed_tutorial",
            ExpressionAttributeValues={":completed_tutorial": completed_tutorial},
            ExpressionAttributeNames={"#completed_tutorial": "completed_tutorial"}
        )

    def get_tutorial_status(self, user_id: str) -> bool:
        if not user_id:
            return False

        try:
            student = self.get_student_by_id(user_id)
            if not student:
                return False
            return student.get('completed_tutorial', False)
        except Exception as e:
            logger.error("Error getting tutorial status for student %s: %s", user_id, e, exc_info=True)
            return False

    def needs_tutorial(self, user_id: str) -> bool:
        return not self.get_tutorial_status(user_id)
