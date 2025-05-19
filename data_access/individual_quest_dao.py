from data_access.base_dao import BaseDAO
from models.individual_quest import IndividualQuest
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import Dict, Any

class IndividualQuestDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("individual_quest")

    def add_individual_quest(self, quest: IndividualQuest) -> None:
        self.table.put_item(Item=quest.to_item())

    def get_individual_quest(self, quest_id: str) -> Dict[str, Any]:
        response = self.table.query(
            KeyConditionExpression=Key("quest_id").eq(quest_id)
        )
        return response["Items"]

    def update_individual_quest(self, quest_id: str, created_at: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        self.table.update_item(
            Key={"quest_id": quest_id, "created_at": created_at},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals
        )

    def delete_individual_quest(self, quest_id: str, created_at: str) -> None:
        self.table.delete_item(Key={"quest_id": quest_id, "created_at": created_at})
