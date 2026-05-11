import logging
import boto3
import os
from botocore.config import Config
from botocore.exceptions import NoCredentialsError, ClientError

logger = logging.getLogger(__name__)

_region = os.getenv("AWS_REGION", "us-east-1")
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=_region,
    endpoint_url=f"https://s3.{_region}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


def upload_to_s3(file_obj, filename=None, folder=None):
    """Uploads a file-like object to S3 and returns its key (not URL)."""
    try:
        if not BUCKET_NAME:
            logger.warning("S3 upload skipped: S3_BUCKET_NAME environment variable not set")
            return None

        key = f"{folder}/{filename or file_obj.filename}" if folder else (filename or file_obj.filename)
        s3.upload_fileobj(
            Fileobj=file_obj,
            Bucket=BUCKET_NAME,
            Key=key,
            ExtraArgs={"ACL": "private"}
        )
        return key

    except (NoCredentialsError, ClientError) as e:
        logger.error("S3 upload failed: %s", e)
        return None


def upload_file_to_s3(file_path, filename=None, folder=None):
    """Uploads a file from a file path to S3 and returns its key (not URL)."""
    try:
        if not BUCKET_NAME:
            logger.warning("S3 upload skipped: S3_BUCKET_NAME environment variable not set")
            return None

        key = f"{folder}/{filename or os.path.basename(file_path)}" if folder else (filename or os.path.basename(file_path))
        s3.upload_file(
            Filename=file_path,
            Bucket=BUCKET_NAME,
            Key=key,
            ExtraArgs={"ACL": "private"}
        )
        return key

    except (NoCredentialsError, ClientError) as e:
        logger.error("S3 upload failed: %s", e)
        return None


def delete_files_from_s3(keys: list) -> None:
    """Delete a list of S3 object keys from the bucket. Logs on failure."""
    if not BUCKET_NAME or not keys:
        return
    objects = [{"Key": k} for k in keys]
    try:
        s3.delete_objects(Bucket=BUCKET_NAME, Delete={"Objects": objects})
    except ClientError as e:
        logger.error("S3 delete_objects failed: %s", e)


def get_file_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Return a presigned S3 URL for the given object key."""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )


def generate_presigned_upload_url(key: str, content_type: str, expires_in: int = 3600) -> str:
    """Return a presigned S3 PUT URL the browser can upload to directly."""
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET_NAME, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in,
    )


def create_multipart_upload(key: str, content_type: str) -> str:
    resp = s3.create_multipart_upload(Bucket=BUCKET_NAME, Key=key, ContentType=content_type)
    return resp["UploadId"]


def generate_presigned_part_url(key: str, upload_id: str, part_number: int, expires_in: int = 3600) -> str:
    return s3.generate_presigned_url(
        "upload_part",
        Params={"Bucket": BUCKET_NAME, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
        ExpiresIn=expires_in,
    )


def complete_multipart_upload(key: str, upload_id: str, parts: list) -> str:
    """parts: [{"PartNumber": int, "ETag": str}, ...]"""
    s3.complete_multipart_upload(
        Bucket=BUCKET_NAME,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )
    return key


def upload_pptx(pptx_bytes: bytes, period_id: str, lesson_id: str) -> str:
    """Upload PowerPoint bytes to S3 and return the key."""
    import io
    key = f"pptx/{period_id}/{lesson_id}.pptx"
    if not BUCKET_NAME:
        logger.warning("S3 upload skipped: S3_BUCKET_NAME not set")
        return key
    s3.upload_fileobj(
        Fileobj=io.BytesIO(pptx_bytes),
        Bucket=BUCKET_NAME,
        Key=key,
        ExtraArgs={
            "ACL": "private",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        },
    )
    return key


def generate_presigned_url(s3_key: str, expiry: int = 900) -> str:
    """Return a presigned S3 GET URL for a PowerPoint file (default 15-min expiry)."""
    return get_file_presigned_url(s3_key, expires_in=expiry)


def download_file_from_s3(key: str, dest_path: str) -> bool:
    """Download an S3 object to dest_path. Returns False on failure."""
    try:
        if not BUCKET_NAME:
            logger.warning("S3 download skipped: S3_BUCKET_NAME environment variable not set")
            return False
        s3.download_file(BUCKET_NAME, key, dest_path)
        return True
    except (NoCredentialsError, ClientError) as e:
        logger.error("S3 download failed for key %s: %s", key, e)
        return False
