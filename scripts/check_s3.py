#!/usr/bin/env python3
"""Run before deploying: python scripts/check_s3.py"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import boto3
from botocore.config import Config

region = os.getenv("AWS_REGION", "us-east-1")
bucket = os.getenv("S3_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=region,
    endpoint_url=f"https://s3.{region}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)

url = s3.generate_presigned_url(
    "upload_part",
    Params={"Bucket": bucket, "Key": "test/check.pdf", "UploadId": "fake", "PartNumber": 1},
    ExpiresIn=60,
)

expected_host = f"{bucket}.s3.{region}.amazonaws.com"
assert expected_host in url, f"FAIL — expected '{expected_host}' in URL\nGot: {url}"
assert f"s3.amazonaws.com/{bucket}" not in url, "FAIL — path-style URL detected"
print(f"OK — {url[:100]}")
