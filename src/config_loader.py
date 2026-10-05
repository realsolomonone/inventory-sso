"""Load inventory configuration and optional account catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import CatalogAccount, InventoryConfig, RoleConfig, TagSpec

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "resource-inventory.yaml"
DEFAULT_ACCOUNTS = Path(__file__).resolve().parent.parent / "config" / "accounts.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data


def parse_tag_specs(raw: list[Any] | None) -> list[TagSpec]:
    specs: list[TagSpec] = []
    for item in raw or []:
        if isinstance(item, str):
            specs.append(TagSpec(key=item))
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        aliases = tuple(str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip())
        allowed = tuple(str(value).strip() for value in (item.get("allowed_values") or []) if str(value).strip())
        specs.append(
            TagSpec(
                key=key,
                aliases=aliases,
                pattern=str(item.get("pattern") or "").strip(),
                allowed_values=allowed,
                example=str(item.get("example") or "").strip(),
                hint=str(item.get("hint") or "").strip(),
            )
        )
    return specs


def load_catalog(path: Path | None = None) -> list[CatalogAccount]:
    target = path or DEFAULT_ACCOUNTS
    if not target.is_file():
        return []
    data = load_yaml(target)
    rows: list[CatalogAccount] = []
    for item in data.get("accounts") or []:
        account_id = str(item.get("account_id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not account_id and not name:
            continue
        rows.append(
            CatalogAccount(
                name=name,
                account_id=account_id,
                environment=str(item.get("environment") or "").strip(),
                aliases=[str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip()],
                notes=str(item.get("notes") or "").strip(),
            )
        )
    return rows


def parse_config(data: dict[str, Any], catalog: list[CatalogAccount] | None = None) -> InventoryConfig:
    identity = data.get("identity") or {}
    scan = data.get("scan") or {}
    tags = data.get("tags") or {}
    upload = data.get("upload") or {}
    role = data.get("role") or {}
    return InventoryConfig(
        ticket=str(data.get("ticket") or "EDL-RESOURCE-INVENTORY"),
        program=str(data.get("program") or "EDL"),
        title=str(data.get("title") or "r-edl-resource-inventory"),
        labels=[str(item) for item in (data.get("labels") or [])],
        partition=str(data.get("partition") or "aws-us-gov"),
        home_region=str(data.get("home_region") or "us-gov-east-1"),
        skip_non_sso=bool(identity.get("skip_non_sso", True)),
        exclude_profiles=[str(item) for item in (identity.get("exclude_profiles") or [])],
        max_workers=int(scan.get("max_workers") or 4),
        include_resource_groups=bool(scan.get("include_resource_groups", True)),
        resource_type_filters=[str(item) for item in (scan.get("resource_type_filters") or []) if str(item).strip()],
        scan_regions=[str(item) for item in (scan.get("regions") or []) if str(item).strip()],
        required_tags=parse_tag_specs(tags.get("required")),
        upload_prefix=str(upload.get("prefix") or "edl-resource-inventory"),
        server_side_encryption=str(upload.get("server_side_encryption") or "AES256"),
        role=RoleConfig(
            name=str(role.get("name") or "r-edl-resource-inventory"),
            description=str(role.get("description") or ""),
            max_session_duration=int(role.get("max_session_duration") or 28800),
            resource_group_account_id=str(role.get("resource_group_account_id") or ""),
            trusted_principal_arns=[str(item) for item in (role.get("trusted_principal_arns") or []) if str(item).strip()],
            trusted_source_account_ids=[
                str(item) for item in (role.get("trusted_source_account_ids") or []) if str(item).strip()
            ],
        ),
        catalog=list(catalog or []),
    )


def load_config(path: Path | None = None, accounts_path: Path | None = None) -> InventoryConfig:
    target = path or DEFAULT_CONFIG
    return parse_config(load_yaml(target), catalog=load_catalog(accounts_path))
