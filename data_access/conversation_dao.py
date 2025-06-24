from data_access.base_dao import BaseDAO
from models.conversation import Conversation
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

class ConversationDAO(BaseDAO):
    def __init__(self):
        """
        Initialize the DAO with the DynamoDB 'conversation' table.
        """
        config = DynamoDBConfig()
        self.table = config.get_table("conversation")

    def add_conversation(self, conversation: Conversation) -> None:
        """
        Add a new conversation record to the table.

        :param conversation: A Conversation model instance.
        :return: None
        """
        self.table.put_item(Item=conversation.to_item())

    def get_conversations_by_thread(self, thread_id: str) -> List[Conversation]:
        """
        Retrieve all conversation records for a specific thread ID.

        :param thread_id: The partition key.
        :return: A list of conversation records (as dictionaries).
        """
        response = self.table.query(
            KeyConditionExpression=Key("thread_id").eq(thread_id)
        )
        return response["Items"]

    def update_conversation(self, thread_id: str, updates: Dict[str, Any]) -> None:
        """
        Update a conversation record by thread_id.

        :param thread_id: The thread_id (partition key).
        :param updates: Dictionary of attributes to update.
        :return: None
        """
        # Query for the conversation(s) with this thread_id
        response = self.table.query(
            KeyConditionExpression=Key("thread_id").eq(thread_id)
        )
        items = response.get("Items", [])
        if not items:
            raise ValueError("Conversation not found.")

        # Assuming only one conversation per thread_id (or update all if multiple)
        for item in items:
            key = {"thread_id": item["thread_id"]}
            # Update the item with new values
            update_expression = "SET " + ", ".join(f"#{k}=:{k}" for k in updates.keys())
            expression_attribute_names = {f"#{k}": k for k in updates.keys()}
            expression_attribute_values = {f":{k}": v for k, v in updates.items()}
            self.table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )

    def delete_conversation(self, thread_id: str) -> None:
        """
        Delete a conversation record using thread_id as key.

        :param thread_id: The partition key.

        :return: None
        """
        self.table.delete_item(Key={"thread_id": thread_id})

    def get_conversation_by_thread_user_conversation_type(self, thread_id: str, user_id: str, conversation_type: str) -> dict:
        """
        Retrieve a single conversation record by thread_id, user_id, and conversation_type.

        :param thread_id: The partition key.
        :param user_id: The user ID.
        :param conversation_type: The type of conversation (e.g., 'profile').
        :return: The conversation record as a dictionary, or None if not found.
        """
        response = self.table.query(
            KeyConditionExpression=Key("thread_id").eq(thread_id)
        )
        for item in response["Items"]:
            if item.get("user_id") == user_id and item.get("conversation_type") == conversation_type:
                return item
        return None
