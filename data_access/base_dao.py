# db/base_dao.py
from data_access.config import DynamoDBConfig
import boto3

# BaseDAO class for common database operations
# 
# IMPORTANT: DAO method return type conventions:
# - get_*_by_id() methods should return a single item (dict) or None
# - get_*_by_*() methods that can return multiple items should return List[Dict]
# - Never use [0] indexing on get_*_by_id() results as they return single items

class BaseDAO:
    def __init__(self, table_name):
        self.config = DynamoDBConfig()
        self.table = self.config.get_table(table_name)

    def key(self, name):
        return boto3.dynamodb.conditions.Key(name)
