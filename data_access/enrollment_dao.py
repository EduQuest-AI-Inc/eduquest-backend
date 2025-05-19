from data_access.base_dao import BaseDAO
from models.enrollment import Enrollment
import boto3
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any

dynamodb = boto3.resource("dynamodb")


class EnrollmentDAO(BaseDAO):
    def __init__(self):
        """
        Initialize the EnrollmentDAO with the DynamoDB 'enrollment' table.
        """
        config = DynamoDBConfig()
        self.table = config.get_table("enrollment")


    def add_enrollment(self, enrollment: Enrollment) -> None:
        """
        Add a new enrollment record to the table.

        :param enrollment: An instance of the Enrollment model.
        """
        self.table.put_item(Item=enrollment.model_dump())


    def get_enrollments_by_class(self, class_id: str) -> List[Enrollment]:
        """
        Retrieve all enrollment records for a given class ID.

        :param class_id: The class identifier (partition key).
        :return: A list of Enrollment instances.
        """
        response = self.table.query(
            KeyConditionExpression=Key("class_id").eq(class_id)
        )

        print(response)

        return response['Items']
    

    def update_enrollment(self, class_id: str, enrolled_at: str, updates: Dict[str, Any]) -> None:
        """
        Update an existing enrollment record using class_id and enrolled_at.

        :param class_id: The class identifier (partition key).
        :param enrolled_at: The timestamp of enrollment (sort key).
        :param updates: Dictionary of fields to update.
            (ex.
                {
                    "student_id": "rkatsura",
                    "semester": "2026 Winter"
                }
            )
        """
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"class_id": class_id, "enrolled_at": enrolled_at},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )


    def delete_enrollment(self, class_id: str, enrolled_at: str) -> None:
        """
        Delete an enrollment record based on class_id and enrolled_at.

        :param class_id: The class identifier (partition key).
        :param enrolled_at: The timestamp of enrollment (sort key).
        """
        self.table.delete_item(Key={"class_id": class_id, "enrolled_at": enrolled_at})