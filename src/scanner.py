"""Read-only inventory via Resource Groups Tagging API and Resource Groups."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from botocore.exceptions import BotoCoreError, ClientError

from .aws_partition import detect_partition, home_region_for_partition
from .identity import lookup_catalog
from .models import (
    AccountResult,
    AccountStatus,
    Inventory,
    InventoryConfig,
    ResourceRecord,
    TagHealth,
)
from .tags import collect_issues, extra_tags, extract_expected, score_tags

logger = logging.getLogger(__name__)

SessionFactory = Callable[[str], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", "ClientError"))


def _service_from_arn(arn: str) -> tuple[str, str]:
    parts = arn.split(":")
    if len(parts) < 6:
        return "", ""
    service = parts[2]
    rest = parts[5]
    resource_type = rest.split("/")[0].split(":")[0]
    return service, resource_type


def _tags_from_mapping(raw: list[dict[str, Any]] | None) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in raw or []:
        key = str(item.get("Key") or "")
        if key:
            tags[key] = str(item.get("Value") or "")
    return tags


def paginate_get_resources(client: Any, resource_type_filters: list[str]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"ResourcesPerPage": 100}
        if token:
            kwargs["PaginationToken"] = token
        if resource_type_filters:
            kwargs["ResourceTypeFilters"] = resource_type_filters
        response = client.get_resources(**kwargs)
        resources.extend(response.get("ResourceTagMappingList") or [])
        token = response.get("PaginationToken") or ""
        if not token:
            break
    return resources


def list_groups(client: Any) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {}
        if token:
            kwargs["NextToken"] = token
        response = client.list_groups(**kwargs)
        groups.extend(response.get("Groups") or [])
        token = response.get("NextToken")
        if not token:
            break
    return groups


def _record_from_mapping(
    mapping: dict[str, Any],
    *,
    profile: str,
    account_id: str,
    account_name: str,
    catalog_environment: str,
    partition: str,
    partition_label: str,
    region: str,
    config: InventoryConfig,
) -> ResourceRecord:
    arn = str(mapping.get("ResourceARN") or "")
    tags = _tags_from_mapping(mapping.get("Tags"))
    service, resource_type = _service_from_arn(arn)
    expected = extract_expected(tags, config.required_tags)
    extras = extra_tags(tags, config.required_tags)
    issues = collect_issues(expected, config.required_tags)
    missing = [issue.key for issue in issues if issue.kind == "missing"]
    invalid = [issue.key for issue in issues if issue.kind == "invalid"]
    health, completeness = score_tags(expected, config.required_tags, issues=issues)
    return ResourceRecord(
        profile=profile,
        account_id=account_id,
        account_name=account_name,
        catalog_environment=catalog_environment,
        partition=partition,
        partition_label=partition_label,
        region=region,
        service=service,
        resource_type=resource_type,
        resource_arn=arn,
        health=health,
        completeness_pct=completeness,
        missing_tags=missing,
        invalid_tags=invalid,
        extra_tags=extras,
        expected=expected,
        all_tags=tags,
        issues=issues,
        kind="resource",
    )


def scan_account(session: Any, profile: str, config: InventoryConfig) -> AccountResult:
    try:
        partition, label, account_id = detect_partition(session)
    except (ClientError, BotoCoreError) as exc:
        code = _error_code(exc) if isinstance(exc, ClientError) else "BotoCoreError"
        status = AccountStatus.DENIED if code in {"AccessDenied", "UnauthorizedOperation"} else AccountStatus.ERROR
        return AccountResult(
            profile=profile,
            account_id="",
            account_name=profile,
            catalog_environment="",
            partition="",
            partition_label="",
            status=status,
            message=str(exc),
        )

    catalog = lookup_catalog(config.catalog, profile=profile, account_id=account_id)
    account_name = catalog.name if catalog and catalog.name else profile
    environment = catalog.environment if catalog else ""
    region = home_region_for_partition(partition, config.home_region)
    if config.scan_regions:
        regions = list(config.scan_regions)
    else:
        regions = [region]

    records: list[ResourceRecord] = []
    groups_total = 0
    try:
        for scan_region in regions:
            tagging = session.client("resourcegroupstaggingapi", region_name=scan_region)
            mappings = paginate_get_resources(tagging, config.resource_type_filters)
            for mapping in mappings:
                records.append(
                    _record_from_mapping(
                        mapping,
                        profile=profile,
                        account_id=account_id,
                        account_name=account_name,
                        catalog_environment=environment,
                        partition=partition,
                        partition_label=label,
                        region=scan_region,
                        config=config,
                    )
                )
            if config.include_resource_groups:
                rg = session.client("resource-groups", region_name=scan_region)
                groups = list_groups(rg)
                groups_total += len(groups)
                for group in groups:
                    arn = str(group.get("GroupArn") or "")
                    records.append(
                        ResourceRecord(
                            profile=profile,
                            account_id=account_id,
                            account_name=account_name,
                            catalog_environment=environment,
                            partition=partition,
                            partition_label=label,
                            region=scan_region,
                            service="resource-groups",
                            resource_type="group",
                            resource_arn=arn or str(group.get("Name") or ""),
                            health=TagHealth.COMPLETE,
                            completeness_pct=100.0,
                            missing_tags=[],
                            invalid_tags=[],
                            extra_tags={},
                            expected={},
                            all_tags={},
                            kind="group",
                            message=str(group.get("Description") or ""),
                        )
                    )
    except ClientError as exc:
        code = _error_code(exc)
        status = AccountStatus.DENIED if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"} else AccountStatus.ERROR
        return AccountResult(
            profile=profile,
            account_id=account_id,
            account_name=account_name,
            catalog_environment=environment,
            partition=partition,
            partition_label=label,
            status=status,
            message=str(exc),
        )
    except BotoCoreError as exc:
        return AccountResult(
            profile=profile,
            account_id=account_id,
            account_name=account_name,
            catalog_environment=environment,
            partition=partition,
            partition_label=label,
            status=AccountStatus.ERROR,
            message=str(exc),
        )

    tagged = [row for row in records if row.kind == "resource"]
    if not tagged:
        status = AccountStatus.EMPTY
        message = "No tagged resources returned by Resource Groups Tagging API"
    else:
        status = AccountStatus.OK
        message = ""

    return AccountResult(
        profile=profile,
        account_id=account_id,
        account_name=account_name,
        catalog_environment=environment,
        partition=partition,
        partition_label=label,
        status=status,
        message=message,
        resources_total=len(tagged),
        groups_total=groups_total,
        resources_complete=sum(1 for row in tagged if row.health == TagHealth.COMPLETE),
        records=records,
    )


def build_narrative(inventory: Inventory) -> list[str]:
    lines = [
        f"{inventory.ticket}: inventoried {inventory.resources_total} tagged resource(s) "
        f"across {len(inventory.accounts)} AWS account(s).",
        f"EDL tag completeness is {inventory.completeness_pct}% "
        f"({inventory.resources_complete} complete, {inventory.resources_missing} need tag fixes).",
        "Role r-edl-resource-inventory grants Resource Groups read APIs and tag:GetResources / GetTagKeys / GetTagValues.",
    ]
    failed = [row for row in inventory.accounts if row.status in {AccountStatus.DENIED, AccountStatus.ERROR}]
    if failed:
        names = ", ".join(row.profile for row in failed)
        lines.append(f"Accounts that could not be fully scanned: {names}.")
    return lines


def default_session_factory(profile: str) -> Any:
    import boto3

    return boto3.Session(profile_name=profile)


def run_inventory(
    config: InventoryConfig,
    profiles: list[str],
    *,
    session_factory: SessionFactory | None = None,
    dry_run: bool = False,
) -> Inventory:
    factory = session_factory or default_session_factory
    accounts: list[AccountResult] = []

    if dry_run:
        for profile in profiles:
            catalog = lookup_catalog(config.catalog, profile=profile, account_id="")
            accounts.append(
                AccountResult(
                    profile=profile,
                    account_id=catalog.account_id if catalog else "",
                    account_name=catalog.name if catalog else profile,
                    catalog_environment=catalog.environment if catalog else "",
                    partition=config.partition,
                    partition_label="",
                    status=AccountStatus.OK,
                    message="dry-run",
                )
            )
        inventory = Inventory(
            ticket=config.ticket,
            program=config.program,
            title=config.title,
            generated_at=_utc_now(),
            accounts=accounts,
            records=[],
            required_tags=list(config.required_tags),
        )
        inventory.narrative = build_narrative(inventory)
        return inventory

    workers = max(1, min(config.max_workers, len(profiles) or 1))
    if workers == 1 or len(profiles) <= 1:
        for profile in profiles:
            accounts.append(scan_account(factory(profile), profile, config))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(scan_account, factory(profile), profile, config): profile for profile in profiles}
            for future in as_completed(futures):
                accounts.append(future.result())
        accounts.sort(key=lambda row: row.profile)

    records = [item for account in accounts for item in account.records]
    inventory = Inventory(
        ticket=config.ticket,
        program=config.program,
        title=config.title,
        generated_at=_utc_now(),
        accounts=sorted(accounts, key=lambda row: row.profile),
        records=records,
        required_tags=list(config.required_tags),
    )
    inventory.narrative = build_narrative(inventory)
    return inventory
