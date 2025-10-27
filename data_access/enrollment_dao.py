from data_access.base_dao import BaseDAO
from models.enrollment import Enrollment
import boto3
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key, Attr
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# dynamodb = boto3.resource("dynamodb")


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
            print(f" Item: {item}, period_id type: {type(item.get('period_id'))}")

    # Add to data_access/enrollment_dao.py
def get_enrollments_by_student_id(self, student_id: str) -> List[Dict[str, Any]]:
    """Get all enrollments for a specific student"""
    try:
        response = self.table.scan(
            FilterExpression=Attr("student_id").eq(student_id)
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"Error querying enrollments by student_id: {e}")
        raise

def is_student_enrolled(self, student_id: str, period_id: str) -> bool:
    """Check if a student is enrolled in a specific period"""
    try:
        response = self.table.scan(
            FilterExpression=Attr("student_id").eq(student_id) & Attr("period_id").eq(period_id)
        )
        return len(response.get("Items", [])) > 0
    except Exception as e:
        print(f"Error checking enrollment: {e}")
        return False