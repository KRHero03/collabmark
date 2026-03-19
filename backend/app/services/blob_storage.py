"""Blob storage service with S3 and local filesystem backends.

When ``S3_ENDPOINT_URL`` is set, uses boto3 to talk to MinIO / S3.
When unset (or empty), falls back to a local filesystem store under
``backend/media/`` so developers can run without MinIO in dev.
"""

from __future__ import annotations

import logging
import shutil
from functools import lru_cache
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def _is_local() -> bool:
    return not settings.s3_endpoint_url


# ---------------------------------------------------------------------------
# S3 backend
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_s3_client():
    """Return a singleton boto3 S3 client configured from app settings."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def _ensure_bucket() -> None:
    """Create the bucket if it doesn't exist yet."""
    from botocore.exceptions import ClientError

    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)
        logger.info("Created S3 bucket: %s", settings.s3_bucket)


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------

_LOCAL_MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent / "media"


def _local_path(key: str) -> Path:
    return _LOCAL_MEDIA_ROOT / key


# ---------------------------------------------------------------------------
# Public API (auto-selects backend)
# ---------------------------------------------------------------------------


def upload(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes and return the object key."""
    if _is_local():
        dest = _local_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info("Stored blob locally: %s (%d bytes)", key, len(data))
        return key

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
    if _is_local():
        root = _local_path(prefix)
        parent = root.parent
        if parent.is_dir():
            for child in parent.iterdir():
                if child.name.startswith(root.name):
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    logger.info("Deleted local blob: %s", child)
        return

    from botocore.exceptions import ClientError

    client = _get_s3_client()
    try:
        resp = client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
        for obj in resp.get("Contents", []):
            client.delete_object(Bucket=settings.s3_bucket, Key=obj["Key"])
            logger.info("Deleted blob: %s", obj["Key"])
    except ClientError:
        logger.warning("Failed to delete blobs with prefix: %s", prefix)


def get_object(key: str) -> dict | None:
    """Read an object from storage. Returns dict with Body and ContentType or None."""
    if _is_local():
        path = _local_path(key)
        if not path.is_file():
            return None
        return {"Body": path.open("rb"), "ContentType": "application/octet-stream"}

    from botocore.exceptions import ClientError

    client = _get_s3_client()
    try:
        return client.get_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError:
        return None


def get_public_url(key: str) -> str:
    """Build the public URL for a stored blob."""
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
