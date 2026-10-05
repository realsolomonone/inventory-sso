"""CSV and JSON deliverables."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Inventory, VerifyReport


def stamp(inventory: Inventory) -> str:
    return (
        inventory.generated_at.replace(":", "")
        .replace(" ", "-")
        .replace("UTC", "")
        .replace("--", "-")
        .strip("-")
    )


def expected_columns(inventory: Inventory) -> list[str]:
    if inventory.required_tags:
        return [spec.key for spec in inventory.required_tags]
    return []


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_data_reports(inventory: Inventory, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = stamp(inventory)
    keys = expected_columns(inventory)
    resource_fields = [
        "Account Name",
        "Account ID",
        "Profile",
        "Kind",
        "Region",
        "Service",
        "Resource Type",
        "ARN",
        "Tag Health",
        "Completeness %",
        "Missing Tags",
        "Invalid Tags",
        *keys,
        "Message",
    ]
    resource_rows = []
    for record in inventory.records:
        row = {
            "Account Name": record.account_name,
            "Account ID": record.account_id,
            "Profile": record.profile,
            "Kind": record.kind,
            "Region": record.region,
            "Service": record.service,
            "Resource Type": record.resource_type,
            "ARN": record.resource_arn,
            "Tag Health": record.health.value,
            "Completeness %": f"{record.completeness_pct:.1f}",
            "Missing Tags": ", ".join(record.missing_tags),
            "Invalid Tags": ", ".join(record.invalid_tags),
            "Message": record.message,
        }
        for key in keys:
            row[key] = record.expected.get(key, "")
        resource_rows.append(row)

    account_rows = [
        {
            "Profile": account.profile,
            "Account ID": account.account_id,
            "Account Name": account.account_name,
            "Status": account.status.value,
            "Resources": str(account.resources_total),
            "Complete": str(account.resources_complete),
            "Need Fix": str(account.resources_needs_fix),
            "Resource Groups": str(account.groups_total),
            "Notes": account.message,
        }
        for account in inventory.accounts
    ]

    paths = {
        "inventory_csv": str(
            _write_csv(output_dir / f"resource-inventory-{tag}.csv", resource_rows, resource_fields)
        ),
        "accounts_csv": str(
            _write_csv(
                output_dir / f"account-summary-{tag}.csv",
                account_rows,
                [
                    "Profile",
                    "Account ID",
                    "Account Name",
                    "Status",
                    "Resources",
                    "Complete",
                    "Need Fix",
                    "Resource Groups",
                    "Notes",
                ],
            )
        ),
    }
    json_path = output_dir / f"resource-inventory-{tag}.json"
    json_path.write_text(json.dumps(inventory_to_dict(inventory), indent=2) + "\n", encoding="utf-8")
    paths["json"] = str(json_path)
    return paths


def inventory_to_dict(inventory: Inventory) -> dict:
    return {
        "ticket": inventory.ticket,
        "program": inventory.program,
        "title": inventory.title,
        "generated_at": inventory.generated_at,
        "resources_total": inventory.resources_total,
        "resources_complete": inventory.resources_complete,
        "completeness_pct": inventory.completeness_pct,
        "narrative": inventory.narrative,
        "accounts": [
            {
                "profile": row.profile,
                "account_id": row.account_id,
                "status": row.status.value,
                "resources_total": row.resources_total,
                "resources_complete": row.resources_complete,
                "message": row.message,
            }
            for row in inventory.accounts
        ],
        "reports": inventory.reports,
    }


def verify_to_dict(report: VerifyReport) -> dict:
    return {
        "ticket": report.ticket,
        "role_name": report.role_name,
        "generated_at": report.generated_at,
        "passed": report.passed_count,
        "failed": report.failed_count,
        "missing": report.missing_count,
        "blocked": report.blocked_count,
        "narrative": report.narrative,
        "accounts": [
            {
                "profile": row.profile,
                "account_id": row.account_id,
                "account_name": row.account_name,
                "status": row.status,
                "role_arn": row.role_arn,
                "created": row.created,
                "message": row.message,
                "probe": row.probe,
                "checks": [
                    {
                        "name": item.name,
                        "passed": item.passed,
                        "expected": item.expected,
                        "found": item.found,
                        "detail": item.detail,
                    }
                    for item in row.checks
                ],
            }
            for row in report.accounts
        ],
        "reports": report.reports,
    }


def write_verify_reports(report: VerifyReport, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = (
        report.generated_at.replace(":", "")
        .replace(" ", "-")
        .replace("UTC", "")
        .replace("--", "-")
        .strip("-")
    )
    account_rows = []
    check_rows = []
    for account in report.accounts:
        account_rows.append(
            {
                "Profile": account.profile,
                "Account ID": account.account_id,
                "Account Name": account.account_name,
                "Overall": account.status,
                "Role ARN": account.role_arn,
                "Created": account.created,
                "Checks passed": str(account.checks_passed),
                "Checks failed": str(account.checks_failed),
                "Probe": account.probe,
                "Notes": account.message,
            }
        )
        for item in account.checks:
            check_rows.append(
                {
                    "Profile": account.profile,
                    "Account ID": account.account_id,
                    "Check": item.name,
                    "Result": "PASS" if item.passed else "FAIL",
                    "Expected": item.expected,
                    "Found": item.found,
                    "Detail": item.detail,
                }
            )
    paths = {
        "verify_accounts_csv": str(
            _write_csv(
                output_dir / f"role-verify-accounts-{tag}.csv",
                account_rows,
                [
                    "Profile",
                    "Account ID",
                    "Account Name",
                    "Overall",
                    "Role ARN",
                    "Created",
                    "Checks passed",
                    "Checks failed",
                    "Probe",
                    "Notes",
                ],
            )
        ),
        "verify_checks_csv": str(
            _write_csv(
                output_dir / f"role-verify-checks-{tag}.csv",
                check_rows,
                ["Profile", "Account ID", "Check", "Result", "Expected", "Found", "Detail"],
            )
        ),
    }
    json_path = output_dir / f"role-verify-{tag}.json"
    json_path.write_text(json.dumps(verify_to_dict(report), indent=2) + "\n", encoding="utf-8")
    paths["verify_json"] = str(json_path)
    return paths
