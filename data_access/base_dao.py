# db/base_dao.py
from data_access.config import DynamoDBConfig
import boto3

class BaseDAO:
    def __init__(self, table_name):
        self.config = DynamoDBConfig()
        self.table = self.config.get_table(table_name)

    def key(self, name):
        return boto3.dynamodb.conditions.Key(name)
