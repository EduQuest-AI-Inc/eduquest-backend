from data_access.base_dao import BaseDAO
from models.period import Period
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

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
        items = response.get("Items", [])
        if not items:
            return None
        
        # Convert DynamoDB item to Period model and then back to dict to ensure proper typing
        period = Period(**items[0])
        return period.model_dump()

    def update_period(self, period_id: str, updates: Dict[str, Any]) -> None:
        # Convert any empty lists to DynamoDB format
        for key, value in updates.items():
            if isinstance(value, list) and not value:
                updates[key] = []  # DynamoDB expects empty lists in this format
        
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}
        
        self.table.update_item(
            Key={"period_id": period_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

    def delete_period(self, period_id: str) -> None:
        self.table.delete_item(Key={"period_id": period_id})

    def get_periods_by_teacher_id(self, teacher_id):
        try:
            response = self.table.scan(
            FilterExpression=Attr("teacher_id").eq(teacher_id)
        )
            items = response.get("Items", [])
            return [Period(**item) for item in items]
        except Exception as e:
            print(f"Error in get_periods_by_teacher_id: {e}")
            return []

    def get_periods_by_school_id(self, school_id: str) -> List[Dict[str, Any]]:
        response = self.table.query(
            IndexName="SchoolPeriodIndex",  # Use GSI
            KeyConditionExpression=Key("school_id").eq(school_id)
        )
        return response.get("Items", [])