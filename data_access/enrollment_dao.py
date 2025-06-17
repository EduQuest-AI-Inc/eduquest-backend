from data_access.base_dao import BaseDAO
from models.enrollment import Enrollment
import boto3
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any

dynamodb = boto3.resource("dynamodb")


class EnrollmentDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("enrollment")
        print(f"Using DynamoDB table: {self.table.name}")

    def add_enrollment(self, enrollment: Enrollment) -> None:
        item = enrollment.model_dump()
        print(f"Adding enrollment: {item}")
        self.table.put_item(Item=item)

    def get_enrollments_by_period(self, period_id: str) -> List[Dict[str, Any]]:
        print("🔍 Querying enrollments by period")
        print(f"🧪 period_id type: {type(period_id)} — value: {period_id}")

        try:
            response = self.table.query(
                KeyConditionExpression=Key("period_id").eq(str(period_id))  # force string
            )
            print("Query response:", response)
            return response.get("Items", [])
        except Exception as e:
            print("Error querying by period_id:", e)
            raise

    def update_enrollment(self, period_id: str, enrolled_at: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        print(f"Updating enrollment with period_id={period_id}, enrolled_at={enrolled_at}")
        self.table.update_item(
            Key={"period_id": str(period_id), "enrolled_at": str(enrolled_at)},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_enrollment(self, period_id: str, enrolled_at: str) -> None:
        print(f"Deleting enrollment with period_id={period_id}, enrolled_at={enrolled_at}")
        self.table.delete_item(Key={
            "period_id": str(period_id),
            "enrolled_at": str(enrolled_at)
        })

    def debug_scan_all(self) -> None:
        print("Scanning all items in enrollment table")
        response = self.table.scan()
        for item in response.get("Items", []):
            print(f"🔎 Item: {item}, period_id type: {type(item.get('period_id'))}")