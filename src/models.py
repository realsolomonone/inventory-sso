"""Data models for r-edl-resource-inventory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccountStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    DENIED = "denied"
    ERROR = "error"


class TagHealth(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID = "invalid"
    UNTAGGED = "untagged"
    ERROR = "error"


@dataclass(frozen=True)
class TagSpec:
    key: str
    aliases: tuple[str, ...] = ()
    pattern: str = ""
    allowed_values: tuple[str, ...] = ()
    example: str = ""
    hint: str = ""


@dataclass
class TagIssue:
    key: str
    kind: str
    current: str
    hint: str
    example: str
    reason: str


@dataclass
class CatalogAccount:
    name: str
    account_id: str
    environment: str = ""
    aliases: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class RoleConfig:
    name: str = "r-edl-resource-inventory"
    description: str = ""
    max_session_duration: int = 28800
    resource_group_account_id: str = ""
    trusted_principal_arns: list[str] = field(default_factory=list)
    trusted_source_account_ids: list[str] = field(default_factory=list)


@dataclass
class InventoryConfig:
    ticket: str
    program: str
    title: str
    labels: list[str]
    partition: str
    home_region: str
    skip_non_sso: bool
    exclude_profiles: list[str]
    max_workers: int
    include_resource_groups: bool
    resource_type_filters: list[str]
    scan_regions: list[str]
    required_tags: list[TagSpec]
    upload_prefix: str
    server_side_encryption: str
    role: RoleConfig = field(default_factory=RoleConfig)
    catalog: list[CatalogAccount] = field(default_factory=list)


@dataclass
class ResourceRecord:
    profile: str
    account_id: str
    account_name: str
    catalog_environment: str
    partition: str
    partition_label: str
    region: str
    service: str
    resource_type: str
    resource_arn: str
    health: TagHealth
    completeness_pct: float
    missing_tags: list[str]
    invalid_tags: list[str]
    extra_tags: dict[str, str]
    expected: dict[str, str]
    all_tags: dict[str, str]
    issues: list[TagIssue] = field(default_factory=list)
    message: str = ""
    kind: str = "resource"

    @property
    def needs_fix(self) -> bool:
        return self.health != TagHealth.COMPLETE


@dataclass
class AccountResult:
    profile: str
    account_id: str
    account_name: str
    catalog_environment: str
    partition: str
    partition_label: str
    status: AccountStatus
    message: str = ""
    resources_total: int = 0
    groups_total: int = 0
    resources_complete: int = 0
    records: list[ResourceRecord] = field(default_factory=list)

    @property
    def resources_needs_fix(self) -> int:
        return sum(1 for row in self.records if row.kind == "resource" and row.needs_fix)


@dataclass
class Inventory:
    ticket: str
    program: str
    title: str
    generated_at: str
    accounts: list[AccountResult]
    records: list[ResourceRecord]
    required_tags: list[TagSpec] = field(default_factory=list)
    narrative: list[str] = field(default_factory=list)
    reports: dict[str, str] = field(default_factory=dict)

    @property
    def resources_total(self) -> int:
        return sum(1 for row in self.records if row.kind == "resource")

    @property
    def resources_complete(self) -> int:
        return sum(1 for row in self.records if row.kind == "resource" and row.health == TagHealth.COMPLETE)

    @property
    def resources_missing(self) -> int:
        return sum(1 for row in self.records if row.kind == "resource" and row.needs_fix)

    @property
    def completeness_pct(self) -> float:
        total = self.resources_total
        if not total:
            return 100.0
        return round(100.0 * self.resources_complete / total, 1)


@dataclass
class CheckResult:
    name: str
    passed: bool
    expected: str = ""
    found: str = ""
    detail: str = ""


@dataclass
class AccountVerify:
    profile: str
    account_id: str
    account_name: str
    partition: str
    role_name: str
    role_arn: str = ""
    created: str = ""
    status: str = "error"
    message: str = ""
    checks: list[CheckResult] = field(default_factory=list)
    probe: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def checks_passed(self) -> int:
        return sum(1 for item in self.checks if item.passed)

    @property
    def checks_failed(self) -> int:
        return sum(1 for item in self.checks if not item.passed)


@dataclass
class VerifyReport:
    generated_at: str
    role_name: str
    ticket: str
    accounts: list[AccountVerify]
    reports: dict[str, str] = field(default_factory=dict)
    narrative: list[str] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for row in self.accounts if row.status == "pass")

    @property
    def failed_count(self) -> int:
        return sum(1 for row in self.accounts if row.status == "fail")

    @property
    def missing_count(self) -> int:
        return sum(1 for row in self.accounts if row.status == "missing")

    @property
    def blocked_count(self) -> int:
        return sum(1 for row in self.accounts if row.status in {"denied", "error"})

    @property
    def overall_status(self) -> str:
        if not self.accounts:
            return "empty"
        if self.failed_count == 0 and self.missing_count == 0 and self.blocked_count == 0:
            return "pass"
        if self.passed_count and (self.failed_count or self.missing_count or self.blocked_count):
            return "partial"
        return "fail"
