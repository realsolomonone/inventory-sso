"""Verify r-edl-resource-inventory exists and matches the screenshot policy."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import unquote

from botocore.exceptions import BotoCoreError, ClientError

from .aws_partition import detect_partition, home_region_for_partition
from .identity import lookup_catalog
from .models import AccountVerify, CheckResult, InventoryConfig, VerifyReport
from .policy import (
    TAG_ACTIONS,
    VIEW_ACTIONS,
    actions_cover,
    as_list,
    expected_inline_policy_name,
    resource_groups_arn,
    statement_by_sid,
    trust_allows_sso,
)

logger = logging.getLogger(__name__)

SessionFactory = Callable[[str], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", "ClientError"))


def parse_iam_document(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    text = unquote(str(raw))
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _check(name: str, passed: bool, expected: str = "", found: str = "", detail: str = "") -> CheckResult:
    return CheckResult(name=name, passed=passed, expected=expected, found=found, detail=detail)


def evaluate_role(
    role: dict[str, Any],
    trust: dict[str, Any],
    inline_policy: dict[str, Any],
    *,
    role_name: str,
    account_id: str,
    partition: str,
    resource_group_account_id: str,
) -> list[CheckResult]:
    view = statement_by_sid(inline_policy, "ViewSpecificResourceGroup") or {}
    tagging = statement_by_sid(inline_policy, "TaggingReadOnly") or {}
    expected_arn = resource_groups_arn(partition, resource_group_account_id or account_id)
    found_arns = as_list(view.get("Resource"))
    return [
        _check("Role exists", True, role_name, str(role.get("RoleName") or ""), str(role.get("Arn") or "")),
        _check(
            "Trust allows IAM Identity Center",
            trust_allows_sso(trust),
            "sts:AssumeRole from aws-reserved/sso.amazonaws.com/*",
            "sso.amazonaws.com present" if trust_allows_sso(trust) else "SSO trust not found",
        ),
        _check(
            "Sid ViewSpecificResourceGroup",
            bool(view) and actions_cover(view.get("Action"), VIEW_ACTIONS),
            ", ".join(VIEW_ACTIONS),
            ", ".join(as_list(view.get("Action"))) or "(missing)",
        ),
        _check(
            "Resource Groups ARN",
            expected_arn in found_arns or any(expected_arn.split(":")[-2] in item for item in found_arns),
            expected_arn,
            ", ".join(found_arns) or "(missing)",
        ),
        _check(
            "Sid TaggingReadOnly",
            bool(tagging) and actions_cover(tagging.get("Action"), TAG_ACTIONS) and "*" in as_list(tagging.get("Resource")),
            ", ".join(TAG_ACTIONS) + " on *",
            ", ".join(as_list(tagging.get("Action"))) or "(missing)",
        ),
    ]


def _probe_tag_api(session: Any, region: str) -> str:
    try:
        client = session.client("resourcegroupstaggingapi", region_name=region)
        client.get_tag_keys()
        return "PASS — tag:GetTagKeys succeeded"
    except ClientError as exc:
        return f"FAIL — {_error_code(exc)}"
    except BotoCoreError as exc:
        return f"FAIL — {exc}"


def verify_account(session: Any, profile: str, config: InventoryConfig, *, probe: bool) -> AccountVerify:
    role_name = config.role.name
    try:
        partition, _label, account_id = detect_partition(session)
    except (ClientError, BotoCoreError) as exc:
        code = _error_code(exc) if isinstance(exc, ClientError) else "BotoCoreError"
        status = "denied" if "AccessDenied" in code else "error"
        return AccountVerify(
            profile=profile,
            account_id="",
            account_name=profile,
            partition="",
            role_name=role_name,
            status=status,
            message=str(exc),
        )

    catalog = lookup_catalog(config.catalog, profile=profile, account_id=account_id)
    account_name = catalog.name if catalog and catalog.name else profile
    region = home_region_for_partition(partition, config.home_region)
    iam = session.client("iam", region_name=region)

    try:
        role = (iam.get_role(RoleName=role_name) or {}).get("Role") or {}
    except ClientError as exc:
        code = _error_code(exc)
        if code in {"NoSuchEntity", "NoSuchEntityException"}:
            return AccountVerify(
                profile=profile,
                account_id=account_id,
                account_name=account_name,
                partition=partition,
                role_name=role_name,
                status="missing",
                message=f"Role {role_name} does not exist. Run: AWS_PROFILE=… terragrunt apply in infra/live/r-edl-resource-inventory",
                checks=[_check("Role exists", False, role_name, "(missing)", code)],
            )
        status = "denied" if "AccessDenied" in code else "error"
        return AccountVerify(
            profile=profile,
            account_id=account_id,
            account_name=account_name,
            partition=partition,
            role_name=role_name,
            status=status,
            message=str(exc),
        )
    except BotoCoreError as exc:
        return AccountVerify(
            profile=profile,
            account_id=account_id,
            account_name=account_name,
            partition=partition,
            role_name=role_name,
            status="error",
            message=str(exc),
        )

    trust = parse_iam_document(role.get("AssumeRolePolicyDocument"))
    inline: dict[str, Any] = {}
    policy_name = expected_inline_policy_name(role_name)
    try:
        raw = iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)
        inline = parse_iam_document(raw.get("PolicyDocument"))
    except ClientError as exc:
        inline = {"_error": _error_code(exc)}

    rg_account = config.role.resource_group_account_id or account_id
    checks = evaluate_role(
        role,
        trust,
        inline,
        role_name=role_name,
        account_id=account_id,
        partition=partition,
        resource_group_account_id=rg_account,
    )
    if inline.get("_error"):
        checks.append(_check("Inline policy", False, policy_name, "(missing)", str(inline["_error"])))
    else:
        checks.append(_check("Inline policy", True, policy_name, policy_name, "GetRolePolicy succeeded"))

    probe_text = ""
    if probe:
        probe_text = _probe_tag_api(session, region)
        checks.append(_check("API probe tag:GetTagKeys", probe_text.startswith("PASS"), "tag:GetTagKeys", probe_text, probe_text))

    created = role.get("CreateDate")
    created_s = created.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(created, "strftime") else str(created or "")
    failed = [item for item in checks if not item.passed]
    return AccountVerify(
        profile=profile,
        account_id=account_id,
        account_name=account_name,
        partition=partition,
        role_name=role_name,
        role_arn=str(role.get("Arn") or ""),
        created=created_s,
        status="fail" if failed else "pass",
        message="" if not failed else "; ".join(item.name for item in failed),
        checks=checks,
        probe=probe_text,
    )


def build_verify_narrative(report: VerifyReport) -> list[str]:
    lines = [
        f"{report.ticket}: verified IAM role {report.role_name} in {len(report.accounts)} account(s).",
        f"{report.passed_count} pass, {report.failed_count} fail, {report.missing_count} missing, {report.blocked_count} denied/error.",
        "Checks: role exists, SSO trust, ViewSpecificResourceGroup, Resource Groups ARN, TaggingReadOnly.",
    ]
    missing = [row.profile for row in report.accounts if row.status == "missing"]
    if missing:
        lines.append("Not created yet: " + ", ".join(missing) + ". Run: AWS_PROFILE=… terragrunt apply in infra/live/r-edl-resource-inventory")
    failed = [row.profile for row in report.accounts if row.status == "fail"]
    if failed:
        lines.append("Policy mismatch: " + ", ".join(failed) + ".")
    return lines


def default_session_factory(profile: str) -> Any:
    import boto3

    return boto3.Session(profile_name=profile)


def run_verify(
    config: InventoryConfig,
    profiles: list[str],
    *,
    session_factory: SessionFactory | None = None,
    probe: bool = True,
    dry_run: bool = False,
) -> VerifyReport:
    factory = session_factory or default_session_factory
    accounts: list[AccountVerify] = []
    if dry_run:
        for profile in profiles:
            accounts.append(
                AccountVerify(
                    profile=profile,
                    account_id="",
                    account_name=profile,
                    partition=config.partition,
                    role_name=config.role.name,
                    status="pass",
                    message="dry-run",
                )
            )
    else:
        workers = max(1, min(config.max_workers, len(profiles) or 1))
        if workers == 1 or len(profiles) <= 1:
            for profile in profiles:
                accounts.append(verify_account(factory(profile), profile, config, probe=probe))
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(verify_account, factory(profile), profile, config, probe=probe): profile
                    for profile in profiles
                }
                for future in as_completed(futures):
                    accounts.append(future.result())
            accounts.sort(key=lambda row: row.profile)

    report = VerifyReport(
        generated_at=_utc_now(),
        role_name=config.role.name,
        ticket=config.ticket,
        accounts=sorted(accounts, key=lambda row: row.profile),
    )
    report.narrative = build_verify_narrative(report)
    return report
