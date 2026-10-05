"""IAM policy for r-edl-resource-inventory — matches the screenshot SIDs and actions."""

from __future__ import annotations

import json
from typing import Any

VIEW_ACTIONS = [
    "resource-groups:GetGroup",
    "resource-groups:GetGroupQuery",
    "resource-groups:ListGroupResources",
    "resource-groups:ListGroups",
    "resource-groups:SearchResources",
]

TAG_ACTIONS = [
    "tag:GetResources",
    "tag:GetTagKeys",
    "tag:GetTagValues",
]

SCREENSHOT_EXAMPLE_ACCOUNT = "053381801543"


def resource_groups_arn(partition: str, account_id: str) -> str:
    return f"arn:{partition}:resource-groups:*:{account_id}:*/*"


def inventory_policy(
    *,
    partition: str = "aws-us-gov",
    account_id: str,
) -> dict[str, Any]:
    """Inline policy document identical to the screenshot, with a live account ID."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ViewSpecificResourceGroup",
                "Effect": "Allow",
                "Action": list(VIEW_ACTIONS),
                "Resource": resource_groups_arn(partition, account_id),
            },
            {
                "Sid": "TaggingReadOnly",
                "Effect": "Allow",
                "Action": list(TAG_ACTIONS),
                "Resource": "*",
            },
        ],
    }


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def statement_by_sid(policy: dict[str, Any], sid: str) -> dict[str, Any] | None:
    for statement in policy.get("Statement") or []:
        if isinstance(statement, dict) and statement.get("Sid") == sid:
            return statement
    return None


def actions_cover(found: Any, required: list[str]) -> bool:
    return set(required).issubset(set(as_list(found)))


def trust_allows_sso(trust: dict[str, Any]) -> bool:
    blob = json.dumps(trust)
    return "sso.amazonaws.com" in blob and "sts:AssumeRole" in blob


def expected_inline_policy_name(role_name: str) -> str:
    return f"{role_name}-policy"
