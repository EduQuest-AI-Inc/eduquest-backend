import boto3
import os
from botocore.exceptions import NoCredentialsError, ClientError

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")  

def upload_to_s3(file_obj, filename=None, folder=None):
    """
    Uploads a file-like object to S3 and returns its key (not URL).
    """
    try:
        key = f"{folder}/{filename or file_obj.filename}" if folder else (filename or file_obj.filename)
        
        s3.upload_fileobj(
            Fileobj=file_obj,
            Bucket=BUCKET_NAME,
            Key=key,
            ExtraArgs={"ACL": "private"}  
        )

        # returning only the key and serving it through our own endpoint in teacher/routes.py
        return key

    except (NoCredentialsError, ClientError) as e:
        print("S3 upload failed:", e)
        return None

def upload_file_to_s3(file_path, filename=None, folder=None):
    """
    Uploads a file from a file path to S3 and returns its key (not URL).
    """
    try:
        key = f"{folder}/{filename or os.path.basename(file_path)}" if folder else (filename or os.path.basename(file_path))
        
        s3.upload_file(
            Filename=file_path,
            Bucket=BUCKET_NAME,
            Key=key,
            ExtraArgs={"ACL": "private"}  
        )

        # returning only the key and serving it through our own endpoint in teacher/routes.py
        return key

    except (NoCredentialsError, ClientError) as e:
        print("S3 upload failed:", e)
        return None