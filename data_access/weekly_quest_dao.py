from data_access.base_dao import BaseDAO
from models.weekly_quest import WeeklyQuest
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any

class WeeklyQuestDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("weekly_quest")

    def add_weekly_quest(self, quest: WeeklyQuest) -> None:
        self.table.put_item(Item=quest.to_item())

    def get_weekly_quests_by_student(self, student_id: str) -> list:
        response = self.table.query(
            KeyConditionExpression=Key("student_id").eq(student_id)
        )
        return response["Items"]

    def update_weekly_quest(self, student_id: str, created_at: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"student_id": student_id, "created_at": created_at},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_weekly_quest(self, student_id: str, created_at: str) -> None:
        self.table.delete_item(Key={"student_id": student_id, "created_at": created_at})
