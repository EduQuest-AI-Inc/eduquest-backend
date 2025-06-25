from data_access.base_dao import BaseDAO
from models.individual_quest import IndividualQuest
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

class IndividualQuestDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("individual_quest")

    def add_individual_quest(self, quest: IndividualQuest) -> None:
        """Add a new individual quest to the database."""
        self.table.put_item(Item=quest.to_item())

    def get_individual_quest_by_id(self, quest_id: str) -> Optional[Dict[str, Any]]:
        """Get an individual quest by its ID."""
        response = self.table.query(
            KeyConditionExpression=Key("quest_id").eq(quest_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def get_quests_by_week(self, week: int) -> List[Dict[str, Any]]:
        """Get all quests for a specific week."""
        response = self.table.scan(
            FilterExpression=Key("Week").eq(week)
        )
        return response.get("Items", [])

    def get_quests_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all quests with a specific status."""
        response = self.table.scan(
            FilterExpression=Key("status").eq(status)
        )
        return response.get("Items", [])

    def update_individual_quest(self, quest_id: str, updates: Dict[str, Any]) -> None:
        """Update an individual quest with new data."""
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}
        
        self.table.update_item(
            Key={"quest_id": quest_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def update_individual_quest_by_individual_id(self, individual_quest_id: str, updates: Dict[str, Any]) -> None:
        """Update an individual quest by its individual_quest_id."""
        # First find the quest by individual_quest_id
        response = self.table.scan(
            FilterExpression=Key("individual_quest_id").eq(individual_quest_id)
        )
        items = response.get("Items", [])
        if not items:
            raise ValueError(f"Individual quest with id {individual_quest_id} not found")
        
        quest_item = items[0]
        quest_id = quest_item["quest_id"]
        
        # Now update using the quest_id
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}
        
        self.table.update_item(
            Key={"quest_id": quest_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def update_quest_grade_and_feedback(self, quest_id: str, grade: str, feedback: str) -> None:
        """Update the grade and feedback for a quest."""
        self.update_individual_quest(quest_id, {
            "grade": grade,
            "feedback": feedback,
            "status": "completed"
        })

    def update_quest_status(self, quest_id: str, status: str) -> None:
        """Update the status of a quest."""
        self.update_individual_quest(quest_id, {"status": status})

    def delete_individual_quest(self, quest_id: str) -> None:
        """Delete an individual quest from the database."""
        self.table.delete_item(Key={"quest_id": quest_id})

    def get_all_quests(self) -> List[Dict[str, Any]]:
        """Get all individual quests from the database."""
        response = self.table.scan()
        return response.get("Items", [])

    def get_quests_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get quests within a specific date range."""
        response = self.table.scan(
            FilterExpression=Key("due_date").between(start_date, end_date)
        )
        return response.get("Items", [])

    def get_quests_by_skills(self, skills: str) -> List[Dict[str, Any]]:
        """Get quests that match specific skills."""
        response = self.table.scan(
            FilterExpression=Key("skills").contains(skills)
        )
        return response.get("Items", [])

    def get_quests_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        """Get all individual quests for a specific student."""
        response = self.table.scan(
            FilterExpression=Key("student_id").eq(student_id)
        )
        return response.get("Items", [])

    def get_quests_by_quest_id(self, quest_id: str) -> List[Dict[str, Any]]:
        """Get all individual quests that share the same quest_id (should be 18 quests)."""
        response = self.table.query(
            KeyConditionExpression=Key("quest_id").eq(quest_id)
        )
        return response.get("Items", [])