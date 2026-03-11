"""S3-compatible blob storage service using boto3.

Provides upload, prefix-delete, and URL generation for binary objects stored in
MinIO (local) or any S3-compatible provider (production). The bucket is
auto-created on first use if it does not already exist.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_s3_client():
    """Return a singleton boto3 S3 client configured from app settings."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def _ensure_bucket() -> None:
    """Create the bucket if it doesn't exist yet."""
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)
        logger.info("Created S3 bucket: %s", settings.s3_bucket)


def upload(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to S3 and return the object key.

    Args:
        key: The S3 object key (e.g. "logos/org123.png").
        data: Raw bytes to upload.
        content_type: MIME type for the object.

    Returns:
        The object key that was stored.
    """
    _ensure_bucket()
    client = _get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    logger.info("Uploaded blob: %s (%d bytes)", key, len(data))
    return key


def delete_prefix(prefix: str) -> None:
    """Delete all objects matching a prefix (e.g. "logos/org123.")."""
    client = _get_s3_client()
    try:
        resp = client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
        for obj in resp.get("Contents", []):
            client.delete_object(Bucket=settings.s3_bucket, Key=obj["Key"])
            logger.info("Deleted blob: %s", obj["Key"])
    except ClientError:
        logger.warning("Failed to delete blobs with prefix: %s", prefix)


def get_public_url(key: str) -> str:
    """Build the public URL for a stored blob.

    In development (MinIO), this is served via the backend's /media proxy.
    In production, this could be a CDN or direct S3 URL.

    Args:
        key: The S3 object key.

    Returns:
        URL path to access the blob (e.g. "/media/logos/org123.png").
    """
    return f"/media/{key}"


MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
}
