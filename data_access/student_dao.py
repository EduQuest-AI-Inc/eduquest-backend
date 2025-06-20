from typing import List, Dict
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Any, Optional
from datetime import datetime, timezone
from models.student import Student

class StudentDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("student")

    def add_student(self, student: Student) -> None:
        self.table.put_item(Item=student.to_item())

    def get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        response = self.table.query(
            KeyConditionExpression=Key("student_id").eq(student_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def update_student(self, student_id: str, updates: Dict[str, Any]) -> None:
        updates["last_login"] = datetime.now(timezone.utc).isoformat()
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}
        self.table.update_item(
            Key={"student_id": str(student_id)},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def delete_student(self, student_id: str) -> None:
        self.table.delete_item(Key={"student_id": student_id})

    def update_long_term_goal(self, student_id: str, period: str, goal: str) -> None:
        """
        Update the long-term goal for a student for a specific period.
        
        Args:
            student_id: The ID of the student
            period: The period for which to update the goal
            goal: The long-term goal text
        """
        print(f"Updating long-term goal for student {student_id}, period {period}")
        print(f"Goal to be saved: {goal}")
        
        # First get the current student data
        student_data = self.get_student_by_id(student_id)
        if not student_data:
            print(f"Error: Student with ID {student_id} not found")
            raise ValueError(f"Student with ID {student_id} not found")
            
        print(f"Current student data: {student_data[0]}")
        
        # Get current long_term_goal or initialize empty dict
        current_goals = student_data[0].get('long_term_goal', {})
        # If current_goals is a list, convert it to a dict
        if isinstance(current_goals, list):
            current_goals = {}
        print(f"Current goals: {current_goals}")
        
        # Update the goal for the specific period
        current_goals[period] = goal
        print(f"Updated goals: {current_goals}")
        
        try:
            # Update the student record
            self.update_student(student_id, {'long_term_goal': current_goals})
            print(f"Successfully updated long-term goal in database")
        except Exception as e:
            print(f"Error updating long-term goal in database: {str(e)}")
            raise
