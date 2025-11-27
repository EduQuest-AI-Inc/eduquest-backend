import boto3
from botocore.exceptions import ClientError
import time

def create_table_with_same_schema(source_table_name, destination_table_name):
    """
    Creates a new DynamoDB table with the same schema as the source table.
    """
    dynamodb_client = boto3.client('dynamodb')
    
    # Describe the source table to get its schema
    try:
        source_description = dynamodb_client.describe_table(TableName=source_table_name)
    except ClientError as e:
        raise ValueError(f"Error describing source table: {e}")
    
    table = source_description['Table']
    
    # Extract necessary parameters for create_table
    create_params = {
        'TableName': destination_table_name,
        'AttributeDefinitions': table['AttributeDefinitions'],
        'KeySchema': table['KeySchema'],
    }
    
    # Add billing mode
    if 'BillingModeSummary' in table:
        create_params['BillingMode'] = table['BillingModeSummary']['BillingMode']
    elif 'ProvisionedThroughput' in table:
        create_params['BillingMode'] = 'PROVISIONED'
        create_params['ProvisionedThroughput'] = table['ProvisionedThroughput']
    else:
        create_params['BillingMode'] = 'PAY_PER_REQUEST'
    
    # Add global secondary indexes if present
    if 'GlobalSecondaryIndexes' in table:
        create_params['GlobalSecondaryIndexes'] = [
            {
                'IndexName': idx['IndexName'],
                'KeySchema': idx['KeySchema'],
                'Projection': idx['Projection'],
                'ProvisionedThroughput': idx.get('ProvisionedThroughput') if create_params['BillingMode'] == 'PROVISIONED' else None
            } for idx in table['GlobalSecondaryIndexes']
        ]
    
    # Add local secondary indexes if present
    if 'LocalSecondaryIndexes' in table:
        create_params['LocalSecondaryIndexes'] = [
            {
                'IndexName': idx['IndexName'],
                'KeySchema': idx['KeySchema'],
                'Projection': idx['Projection']
            } for idx in table['LocalSecondaryIndexes']
        ]
    
    # Remove ProvisionedThroughput from GSIs if billing mode is PAY_PER_REQUEST
    if create_params.get('BillingMode') == 'PAY_PER_REQUEST':
        if 'GlobalSecondaryIndexes' in create_params:
            for gsi in create_params['GlobalSecondaryIndexes']:
                gsi.pop('ProvisionedThroughput', None)
        create_params.pop('ProvisionedThroughput', None)
    
    # Create the new table
    try:
        dynamodb_client.create_table(**create_params)
    except ClientError as e:
        raise ValueError(f"Error creating destination table: {e}")
    
    # Wait for the table to be created
    waiter = dynamodb_client.get_waiter('table_exists')
    waiter.wait(TableName=destination_table_name)
    print(f"Table '{destination_table_name}' created successfully.")

def copy_items(source_table_name, destination_table_name):
    """
    Copies all items from the source table to the destination table.
    """
    dynamodb_resource = boto3.resource('dynamodb')
    source_table = dynamodb_resource.Table(source_table_name)
    destination_table = dynamodb_resource.Table(destination_table_name)
    
    # Scan the source table and copy items in batches
    with destination_table.batch_writer() as batch:
        last_evaluated_key = None
        while True:
            scan_params = {}
            if last_evaluated_key:
                scan_params['ExclusiveStartKey'] = last_evaluated_key
            
            response = source_table.scan(**scan_params)
            items = response.get('Items', [])
            
            for item in items:
                batch.put_item(Item=item)
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
    
    print(f"All items copied from '{source_table_name}' to '{destination_table_name}'.")

def main(source_table_name, destination_table_name):
    create_table_with_same_schema(source_table_name, destination_table_name)
    copy_items(source_table_name, destination_table_name)

# Example usage
if __name__ == "__main__":
    main('conversation', 'test_conversation')
    main('enrollment', 'test_enrollment')
    main('individual_quest', 'test_individual_quest')
    main('period', 'test_period')
    main('school', 'test_school')
    main('session', 'test_session')
    main('student', 'test_student')
    main('teacher', 'test_teacher')
    main('waitlist', 'test_waitlist')
    main('weekly_quest', 'test_weekly_quest')