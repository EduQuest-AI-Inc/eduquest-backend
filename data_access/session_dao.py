from data_access.base_dao import BaseDAO
from models.session import Session
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class SessionDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table("session")

    def add_session(self, session: Session) -> None:
        self.table.put_item(Item=session.to_item())

    def get_sessions_by_auth_token(self, auth_token: str) -> List[Session]:
        response = self.table.query(
            KeyConditionExpression=Key("auth_token").eq(auth_token)
        )
        return response["Items"]

    def update_session(self, auth_token: str, user_id: str, updates: Dict[str, Any]) -> None:
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
        expr_attr_vals = {f":{k}": v for k, v in updates.items()}
        expr_attr_names = {f"#{k}": k for k in updates}

        self.table.update_item(
            Key={"auth_token": auth_token, "user_id": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )


    def delete_session(self, auth_token: str, user_id: str) -> None:
        self.table.delete_item(Key={"auth_token": auth_token, "user_id": user_id})