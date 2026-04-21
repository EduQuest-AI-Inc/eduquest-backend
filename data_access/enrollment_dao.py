import logging
from data_access.base_dao import BaseDAO
from models.enrollment import Enrollment
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EnrollmentDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("enrollment")

    def add_enrollment(self, enrollment: Enrollment) -> None:
        self.table.put_item(Item=enrollment.model_dump())

    def get_enrollments_by_period(self, period_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.table.query(
                KeyConditionExpression=Key("period_id").eq(str(period_id))
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error("Error querying enrollments by period_id: %s", e, exc_info=True)
            raise

    def get_enrollments_by_student(self, user_id: str) -> List[Dict[str, Any]]:
        response = self.table.scan(
            FilterExpression=Key("user_id").eq(user_id)
        )
        return response.get("Items", [])

    def update_enrollment(self, period_id: str, enrolled_at: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"period_id": str(period_id), "enrolled_at": str(enrolled_at)},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_enrollment(self, period_id: str, enrolled_at: str) -> None:
        self.table.delete_item(Key={
            "period_id": str(period_id),
            "enrolled_at": str(enrolled_at)
        })
