# Updated data_access/config.py
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
        
        # Table name mappings - use test tables if environment variable is set
        self.use_test_tables = os.getenv('USE_TEST_TABLES', 'false').lower() == 'true'
        self.table_prefix = 'test_' if self.use_test_tables else ''

    def get_table(self, table_name: str):
        full_table_name = f"{self.table_prefix}{table_name}"
        return self.dynamodb.Table(full_table_name)