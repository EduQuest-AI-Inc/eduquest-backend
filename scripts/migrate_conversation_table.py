#!/usr/bin/env python3
"""
One-off migration: rename DynamoDB ``conversation`` table partition key
from ``thread_id`` to ``conversation_id``.

DynamoDB does not allow changing key schemas in place, so this script:
  1. Creates a new table ``conversation_v2`` with partition key ``conversation_id``.
  2. Scans every item in the old ``conversation`` table.
  3. Copies each item into ``conversation_v2``, renaming the key attribute.

After running this script and verifying the data:
  - Update ``ConversationDAO`` to point at ``conversation_v2``
    (already done — it reads the CONVERSATION_TABLE_NAME env var).
  - Keep the old table as a backup until you're confident.

Usage:
    cd eduquest-backend
    python scripts/migrate_conversation_table.py
"""
import os
import sys
import boto3
from dotenv import load_dotenv

load_dotenv()

OLD_TABLE = os.getenv("CONVERSATION_TABLE_NAME", "conversation")
NEW_TABLE = os.getenv("CONVERSATION_TABLE_NAME_V2", "conversation_v2")

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION", "us-east-2"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
ddb_client = dynamodb.meta.client


def create_new_table():
    """Create conversation_v2 with partition key ``conversation_id``."""
    existing = ddb_client.list_tables()["TableNames"]
    if NEW_TABLE in existing:
        print(f"Table '{NEW_TABLE}' already exists — skipping creation.")
        return

    print(f"Creating table '{NEW_TABLE}' ...")
    ddb_client.create_table(
        TableName=NEW_TABLE,
        KeySchema=[
            {"AttributeName": "conversation_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "conversation_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    waiter = ddb_client.get_waiter("table_exists")
    waiter.wait(TableName=NEW_TABLE)
    print(f"Table '{NEW_TABLE}' is ACTIVE.")


def migrate_items():
    """Scan old table and batch-write into new table."""
    old_table = dynamodb.Table(OLD_TABLE)
    new_table = dynamodb.Table(NEW_TABLE)

    scan_kwargs = {}
    migrated = 0

    while True:
        response = old_table.scan(**scan_kwargs)
        items = response.get("Items", [])

        with new_table.batch_writer() as batch:
            for item in items:
                thread_id = item.pop("thread_id", None)
                if thread_id is None:
                    print(f"  SKIP item (no thread_id): {item}")
                    continue
                item["conversation_id"] = thread_id
                batch.put_item(Item=item)
                migrated += 1

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    print(f"Migrated {migrated} items from '{OLD_TABLE}' -> '{NEW_TABLE}'.")


def main():
    print(f"Old table : {OLD_TABLE}")
    print(f"New table : {NEW_TABLE}")
    print()

    create_new_table()
    migrate_items()

    print()
    print("Done!  Next steps:")
    print(f"  1. Verify data in '{NEW_TABLE}'.")
    print(f"  2. Set CONVERSATION_TABLE_NAME={NEW_TABLE} in .env (or rename tables).")
    print(f"  3. Keep '{OLD_TABLE}' as backup until validated.")


if __name__ == "__main__":
    main()
