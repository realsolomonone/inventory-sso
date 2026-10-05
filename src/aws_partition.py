"""Detect AWS partition for correct regional API endpoints.

Adapted from ~/workspace/s3-taggings/src/aws_partition.py.
"""

from __future__ import annotations

import boto3

PARTITION_LABELS = {
    "aws": "AWS Commercial",
    "aws-us-gov": "AWS GovCloud (US)",
    "aws-iso": "AWS ISO",
    "aws-iso-b": "AWS ISO (US)",
    "aws-cn": "AWS China",
}

DEFAULT_HOME_REGION = {
    "aws": "us-east-1",
    "aws-us-gov": "us-gov-east-1",
    "aws-iso": "us-iso-east-1",
    "aws-iso-b": "us-iso-b-east-1",
    "aws-cn": "cn-north-1",
}


def partition_from_arn(arn: str) -> str:
    if not arn.startswith("arn:"):
        return "aws"
    part = arn.split(":", 2)[1]
    return part if part else "aws"


def partition_label(partition: str) -> str:
    return PARTITION_LABELS.get(partition, partition)


def home_region_for_partition(partition: str, override: str | None = None) -> str:
    if override:
        return override
    return DEFAULT_HOME_REGION.get(partition, "us-east-1")


def detect_partition(session: boto3.Session) -> tuple[str, str, str]:
    identity = session.client("sts").get_caller_identity()
    arn = identity.get("Arn", "")
    partition = partition_from_arn(arn)
    return partition, partition_label(partition), identity.get("Account", "")


def validate_region_for_partition(partition: str, region: str) -> str | None:
    if partition == "aws-us-gov" and not region.startswith("us-gov"):
        return (
            f"Region '{region}' is not a GovCloud region but account partition is "
            f"{partition_label(partition)}."
        )
    if partition == "aws" and region.startswith("us-gov"):
        return (
            f"Region '{region}' is GovCloud but account partition is "
            f"{partition_label(partition)}."
        )
    return None
