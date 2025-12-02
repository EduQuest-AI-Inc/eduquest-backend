from data_access.base_dao import BaseDAO
from models.guardrail_flag import GuardrailFlag
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key, Attr
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class GuardrailFlagDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("guardrail_flag")

    def add_flag(self, flag: GuardrailFlag) -> None:
        self.table.put_item(Item=flag.to_item())

    def get_flag_by_id(self, flag_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("flag_id").eq(flag_id)
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def get_flags_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        response = self.table.scan(
            FilterExpression=Attr("student_id").eq(student_id)
        )
        return response.get("Items", [])

    def get_flags_by_period(self, period_id: str) -> List[Dict[str, Any]]:
        response = self.table.scan(
            FilterExpression=Attr("period_id").eq(period_id)
        )
        return response.get("Items", [])

    def get_unresolved_flags(self) -> List[Dict[str, Any]]:
        response = self.table.scan(
            FilterExpression=Attr("resolved").eq(False)
        )
        return response.get("Items", [])

    def update_flag(self, flag_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"flag_id": flag_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_flag(self, flag_id: str) -> None:
        self.table.delete_item(Key={"flag_id": flag_id})
