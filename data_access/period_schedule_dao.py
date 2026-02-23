from data_access.base_dao import BaseDAO
from models.period_schedule import PeriodSchedule
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


class PeriodScheduleDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("period_schedule")

    def add_period_schedule(self, period_schedule: PeriodSchedule) -> None:
        """Create or replace a period schedule."""
        self.table.put_item(Item=period_schedule.to_item())

    def get_by_period_id(self, period_id: str) -> Optional[PeriodSchedule]:
        """Get the schedule for a period."""
        response = self.table.query(
            KeyConditionExpression=Key("period_id").eq(period_id)
        )
        items = response.get("Items", [])
        if items:
            return PeriodSchedule.from_item(items[0])
        return None

    def update_period_schedule(self, period_id: str, updates: Dict[str, Any]) -> None:
        """Update specific fields of a period schedule."""
        # Always update last_updated_at
        updates["last_updated_at"] = datetime.now(timezone.utc).isoformat()

        update_expr_parts = []
        expr_attr_vals = {}
        expr_attr_names = {}

        for k, v in updates.items():
            attr_name = f"#{k}"
            attr_value = f":{k}"
            update_expr_parts.append(f"{attr_name} = {attr_value}")
            expr_attr_vals[attr_value] = v
            expr_attr_names[attr_name] = k

        update_expr = "SET " + ", ".join(update_expr_parts)

        self.table.update_item(
            Key={"period_id": period_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def delete_period_schedule(self, period_id: str) -> None:
        """Delete a period schedule."""
        self.table.delete_item(Key={"period_id": period_id})
