from functools import lru_cache
from typing import Any, BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings


@lru_cache
def get_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def ensure_bucket() -> None:
    client = get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_fileobj(fileobj: BinaryIO, key: str, content_type: str) -> None:
    """Stream the file to S3 (multipart under the hood for large files)."""
    get_client().upload_fileobj(
        fileobj, settings.s3_bucket, key, ExtraArgs={"ContentType": content_type}
    )


def delete_object(key: str) -> None:
    get_client().delete_object(Bucket=settings.s3_bucket, Key=key)
