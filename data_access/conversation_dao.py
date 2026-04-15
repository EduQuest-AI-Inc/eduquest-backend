import os
from data_access.base_dao import BaseDAO
from models.conversation import Conversation
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CONVERSATION_TABLE = os.getenv("CONVERSATION_TABLE_NAME", "conversation")

class ConversationDAO(BaseDAO):
    def __init__(self):
        config = DynamoDBConfig()
        self.table = config.get_table(CONVERSATION_TABLE)

    def add_conversation(self, conversation: Conversation) -> None:
        self.table.put_item(Item=conversation.to_item())

    def get_conversations_by_id(self, conversation_id: str) -> List[dict]:
        """
        Retrieve all conversation records for a specific conversation ID.

        :param conversation_id: The partition key.
        :return: A list of conversation records (as dictionaries).
        """
        response = self.table.query(
            KeyConditionExpression=Key("conversation_id").eq(conversation_id)
        )
        return response["Items"]

    def update_conversation(self, conversation_id: str, updates: Dict[str, Any]) -> None:
        """
        Update a conversation record by conversation_id.

        :param conversation_id: The partition key.
        :param updates: Dictionary of attributes to update.
        """
        response = self.table.query(
            KeyConditionExpression=Key("conversation_id").eq(conversation_id)
        )
        items = response.get("Items", [])
        if not items:
            raise ValueError("Conversation not found.")

        for item in items:
            key = {"conversation_id": item["conversation_id"]}
            update_expression = "SET " + ", ".join(f"#{k}=:{k}" for k in updates.keys())
            expression_attribute_names = {f"#{k}": k for k in updates.keys()}
            expression_attribute_values = {f":{k}": v for k, v in updates.items()}
            self.table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )

    def delete_conversation(self, conversation_id: str) -> None:
        self.table.delete_item(Key={"conversation_id": conversation_id})

    def get_conversation_by_id_user_type(self, conversation_id: str, user_id: str, conversation_type: str) -> dict:
        """
        Retrieve a single conversation record by conversation_id, user_id,
        and conversation_type.

        :param conversation_id: The partition key.
        :param user_id: The user ID.
        :param conversation_type: The type of conversation (e.g., 'profile').
        :return: The conversation record as a dictionary, or None if not found.
        """
        response = self.table.query(
            KeyConditionExpression=Key("conversation_id").eq(conversation_id)
        )
        for item in response["Items"]:
            if item.get("user_id") == user_id and item.get("conversation_type") == conversation_type:
                return item
        return None
