from typing import List, Dict
from data_access.base_dao import BaseDAO
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Any, Optional
from datetime import datetime, timezone
from models.student import Student
from dotenv import load_dotenv

load_dotenv()

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
            
        print(f"Current student data: {student_data}")
        
        # Get current long_term_goal or initialize empty dict
        current_goals = student_data.get('long_term_goal', {})
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

    def update_tutorial_status(self, student_id: str, completed_tutorial: bool) -> None:
        """
        Update tutorial completion status for a student.
        
        Args:
            student_id: The ID of the student
            completed_tutorial: Whether the tutorial is completed
        """
        if not student_id:
            raise ValueError("Student ID cannot be empty")
        
        if not isinstance(completed_tutorial, bool):
            raise ValueError("completed_tutorial must be a boolean value")
        
        try:
            # First check if student exists
            existing_student = self.get_student_by_id(student_id)
            if not existing_student:
                raise ValueError(f"Student with ID {student_id} not found")
            
            # Use direct update without automatic last_login timestamp for tutorial updates
            update_expr = "SET #completed_tutorial = :completed_tutorial"
            expr_attr_vals = {":completed_tutorial": completed_tutorial}
            expr_attr_names = {"#completed_tutorial": "completed_tutorial"}
            
            self.table.update_item(
                Key={"student_id": str(student_id)},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_names
            )
            print(f"Successfully updated tutorial status for student {student_id}: completed={completed_tutorial}")
        except ValueError as ve:
            print(f"Validation error updating tutorial status: {ve}")
            raise
        except Exception as e:
            print(f"DynamoDB error updating tutorial status for student {student_id}: {e}")
            raise

    def get_tutorial_status(self, student_id: str) -> bool:
        """
        Get tutorial completion status for a student.
        
        Args:
            student_id: The ID of the student
        Returns:
            True if tutorial is completed, False otherwise
        """
        if not student_id:
            print("Warning: Empty student_id provided to get_tutorial_status")
            return False
        
        try:
            student = self.get_student_by_id(student_id)
            if not student:
                print(f"Student with ID {student_id} not found")
                return False
            
            tutorial_status = student.get('completed_tutorial', False)
            print(f"Tutorial status for student {student_id}: {tutorial_status}")
            return tutorial_status
        except Exception as e:
            print(f"Error getting tutorial status for student {student_id}: {e}")
            return False

    def needs_tutorial(self, student_id: str) -> bool:
        """
        Check if a student needs to complete the tutorial.
        
        Args:
            student_id: The ID of the student
        Returns:
            True if student needs tutorial, False otherwise
        """
        return not self.get_tutorial_status(student_id)

    # TODO: create GSI for school_id
    def get_students_by_school_id(self, school_id: str) -> List[Dict[str, Any]]:
        response = self.table.query(
            IndexName="school_id-index",  # Use GSI
            KeyConditionExpression=Key("school_id").eq(school_id)
        )
        return response.get("Items", [])