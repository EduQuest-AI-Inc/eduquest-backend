#!/usr/bin/env python3
"""Apply S3 CORS config to the uploads bucket: python scripts/deploy_s3_cors.py"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import boto3

s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
bucket = os.getenv("S3_BUCKET_NAME")

s3.put_bucket_cors(
    Bucket=bucket,
    CORSConfiguration={"CORSRules": [{
        "AllowedOrigins": [
            "https://eduquestai.org",
            "https://www.eduquestai.org",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
        ],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000,
    }]},
)
print(f"CORS config applied to {bucket}.")
