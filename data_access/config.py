import os
import boto3
from dotenv import load_dotenv
from pathlib import Path

# Ensure we load the .env that lives in the backend directory, even when CWD is project root
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / '.env')

class DynamoDBConfig:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=os.getenv('AWS_REGION', 'us-east-2'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        )

    def get_table(self, table_name: str):
        return self.dynamodb.Table(table_name)
