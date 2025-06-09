from data_access.base_dao import BaseDAO
from models.conversation import Conversation
from data_access.config import DynamoDBConfig
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any
from datetime import datetime, timezone

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

    def update_conversation(self, thread_id: str, last_updated_at: str, updates: Dict[str, Any]) -> str:
        """
        Update a conversation record, including changing the last_updated_at (sort key).
        Since primary and sort keys are immutable, this creates a new item and deletes the old one.

        :param thread_id: The original thread_id (partition key).
        :param last_updated_at: The original last_updated_at (sort key).
        :param updates: Dictionary of attributes to update.
        :return: The new last_updated_at timestamp as a string.
        """
        # Step 1: Get existing item
        response = self.table.get_item(Key={
            "thread_id": thread_id,
            "last_updated_at": last_updated_at
        })

        item = response.get("Item")
        if not item:
            raise ValueError("Conversation not found.")

        # Step 2: Apply updates
        item.update(updates)

        # Step 3: Update last_updated_at to now
        new_timestamp = datetime.now(timezone.utc).isoformat()
        item["last_updated_at"] = new_timestamp

        # Step 4: Add new item
        self.table.put_item(Item=item)

        # Step 5: Delete old item
        self.table.delete_item(Key={
            "thread_id": thread_id,
            "last_updated_at": last_updated_at
        })

        return new_timestamp

    def delete_conversation(self, thread_id: str, last_updated_at: str) -> None:
        """
        Delete a conversation record using thread_id and last_updated_at as key.

        :param thread_id: The partition key.
        :param last_updated_at: The sort key.
        :return: None
        """
        self.table.delete_item(Key={"thread_id": thread_id, "last_updated_at": last_updated_at})

    def get_conversation(self, thread_id: str, user_id: str, conversation_type: str) -> dict:
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
