from data_access.base_dao import BaseDAO
from models.weekly_quest import WeeklyQuest
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any
from datetime import datetime, timezone

class WeeklyQuestDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("weekly_quest")

    def add_weekly_quest(self, quest: WeeklyQuest) -> None:
        self.table.put_item(Item=quest.to_item())

    def get_weekly_quest_by_id(self, weekly_quest_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("weekly_quest_id").eq(weekly_quest_id)
        )
        return response["Items"]

    def update_weekly_quest(self, weekly_quest_id: str, updates: Dict[str, Any]) -> None:
        update_expr_parts = []
        expr_attr_vals = {}
        expr_attr_names = {}

        # Add automatic last_updated_at timestamp
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
            "Key": {"weekly_quest_id": weekly_quest_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_attr_vals
        }

        if expr_attr_names:
            kwargs["ExpressionAttributeNames"] = expr_attr_names

        self.table.update_item(**kwargs)


    def delete_weekly_quest(self, weekly_quest_id: str, created_at: str) -> None:
        self.table.delete_item(Key={"weekly_quest_id": weekly_quest_id, "created_at": created_at})
