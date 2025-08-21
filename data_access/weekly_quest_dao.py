from data_access.base_dao import BaseDAO
from models.weekly_quest import WeeklyQuest
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key, Attr
from typing import Dict, Any, List
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

class WeeklyQuestDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("weekly_quest")

    def add_weekly_quest(self, quest: WeeklyQuest) -> None:
        self.table.put_item(Item=quest.to_item())

    def get_weekly_quest_by_id(self, quest_id: str) -> WeeklyQuest:
        response = self.table.query(
            KeyConditionExpression=Key("quest_id").eq(quest_id)
        )
        items = response.get("Items", [])
        if items:
            return WeeklyQuest.from_item(items[0])
        return None

    def update_weekly_quest(self, quest_id: str, updates: Dict[str, Any]) -> None:
        update_expr_parts = []
        expr_attr_vals = {}
        expr_attr_names = {}

        now = datetime.now(timezone.utc).isoformat()
        updates["last_updated_at"] = now

        for k, v in updates.items():
            attr_name = f"#{k}" if k in ["year", "last_updated_at"] else k
            attr_value = f":{k}"
            update_expr_parts.append(f"{attr_name} = {attr_value}")
            expr_attr_vals[attr_value] = v
            if k in ["year", "last_updated_at"]:
                expr_attr_names[attr_name] = k

        update_expr = "SET " + ", ".join(update_expr_parts)

        kwargs = {
            "Key": {"quest_id": quest_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_attr_vals
        }

        if expr_attr_names:
            kwargs["ExpressionAttributeNames"] = expr_attr_names

        self.table.update_item(**kwargs)

    def update_individual_quest_in_weekly_quest(self, quest_id: str, individual_quest_id: str, updates: Dict[str, Any]) -> None:
        """Update a specific individual quest within a weekly quest list."""
        weekly_quest = self.get_weekly_quest_by_id(quest_id)
        if not weekly_quest:
            raise ValueError(f"Weekly quest with id {quest_id} not found")
        
        quest_updated = False
        for quest in weekly_quest.quests:
            if quest.individual_quest_id == individual_quest_id:
                for key, value in updates.items():
                    setattr(quest, key, value)
                quest.last_updated_at = datetime.now(timezone.utc).isoformat()
                quest_updated = True
                break
        
        if not quest_updated:
            raise ValueError(f"Individual quest with id {individual_quest_id} not found in weekly quest {quest_id}")
        
        self.add_weekly_quest(weekly_quest)

    def delete_weekly_quest(self, quest_id: str) -> None:
        self.table.delete_item(Key={"quest_id": quest_id})

    def get_quests_by_student_and_period(self, student_id: str, period_id: str) -> List[WeeklyQuest]:
        """Get all weekly quests for a student in a specific period."""
        composite_key = f"{student_id}#{period_id}"
        response = self.table.query(
            IndexName="student_period_index",
            KeyConditionExpression=Key("student_period_key").eq(composite_key)
        )
        items = response.get("Items", [])
        return [WeeklyQuest.from_item(item) for item in items]

    def get_weekly_quest_by_student_and_period(self, student_id: str, period_id: str) -> WeeklyQuest:
        """Get the weekly quest for a student in a specific period (should be only one)."""
        import time
        
        print(f"DEBUG: Searching for weekly quest with student_id={student_id}, period_id={period_id}")
        
        # Implement retry logic with exponential backoff for eventual consistency on GSI
        max_retries = 3
        base_delay = 0.5  # Start with 500ms
        
        for attempt in range(max_retries + 1):
            weekly_quests = self.get_quests_by_student_and_period(student_id, period_id)
            print(f"DEBUG: Attempt {attempt + 1}: Found {len(weekly_quests)} weekly quests")
            
            if weekly_quests:
                print(f"DEBUG: Returning first weekly quest with quest_id={weekly_quests[0].quest_id}")
                return weekly_quests[0]
            
            # If not found and we have retries left, wait with exponential backoff
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"DEBUG: No weekly quest found on attempt {attempt + 1}, waiting {delay}s before retry...")
                time.sleep(delay)
        
        print("DEBUG: No weekly quests found after all retries, returning None")
        return None