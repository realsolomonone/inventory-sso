"""Upload inventory reports to S3 with SSE and HTML content types.

Adapted from ~/workspace/s3-taggings/src/s3_uploader.py.
"""

from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)

_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


def validate_bucket_name(bucket: str) -> str:
    name = (bucket or "").strip()
    if not _BUCKET_RE.match(name) or ".." in name:
        raise ValueError(f"Invalid S3 bucket name: {bucket!r}")
    return name


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".csv":
        return "text/csv; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def sync_directory_to_s3(
    local_dir: Path,
    bucket: str,
    prefix: str,
    region: str,
    profile: str | None,
    dry_run: bool,
    server_side_encryption: str = "AES256",
) -> int:
    local_dir = local_dir.resolve()
    if not local_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {local_dir}")

    bucket = validate_bucket_name(bucket)
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    s3 = session.client("s3", region_name=region)
    uploaded = 0
    prefix_clean = prefix.strip("/")

    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        key = f"{prefix_clean}/{rel}" if prefix_clean else rel
        if dry_run:
            print(f"  [dry-run] s3://{bucket}/{key}")
            uploaded += 1
            continue
        extra: dict[str, str] = {"ContentType": _content_type(path)}
        if path.suffix.lower() == ".html":
            extra["ContentDisposition"] = "inline"
        if server_side_encryption:
            extra["ServerSideEncryption"] = server_side_encryption
        s3.upload_file(str(path), bucket, key, ExtraArgs=extra)
        uploaded += 1
        logger.info("Uploaded s3://%s/%s", bucket, key)
    return uploaded
