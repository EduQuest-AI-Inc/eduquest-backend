from data_access.base_dao import BaseDAO
from models.period import Period
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr
from typing import Dict, Any

class PeriodDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("period")

    def add_period(self, period: Period) -> None:
        self.table.put_item(Item=period.to_item())

    def get_period_by_id(self, period_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("period_id").eq(period_id)
        )
        return response["Items"]

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"period_id": period_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_period(self, period_id: str) -> None:
        self.table.delete_item(Key={"period_id": period_id})

    def get_periods_by_teacher_id(self, teacher_id):
        try:
            response = self.table.scan(
                FilterExpression=Attr("teacher_id").eq(teacher_id)
            )
            items = response.get("Items", [])

            for item in items:
                return [Period(**item) for item in items]
        except Exception as e:
            print(f"Error in get_periods_by_teacher_id: {e}")
            return []