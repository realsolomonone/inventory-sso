#!/usr/bin/env python3
"""
EDL resource inventory — production CLI.

Creates / operates the r-edl-resource-inventory SSO role (Terragrunt) and
inventories tagged resources via Resource Groups Tagging API.

Uses every IAM Identity Center profile in ~/.aws/config — same SSO contract as
~/workspace/s3-taggings (python edl_s3_tag_inventory.py login --all).

Usage:
  python edl_resource_inventory.py setup --install
  python edl_resource_inventory.py doctor
  python edl_resource_inventory.py login --all
  python edl_resource_inventory.py profiles --check
  cd infra/live/r-edl-resource-inventory && AWS_PROFILE=… terragrunt apply
  terragrunt output verification
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Sequence

__version__ = "1.0.0"

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = APP_ROOT / "config" / "resource-inventory.yaml"
DEFAULT_ACCOUNTS = APP_ROOT / "config" / "accounts.yaml"
DEFAULT_OUTPUT = APP_ROOT / "reports"
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-gov-east-1")
LIVE_DIR = APP_ROOT / "infra" / "live"

log = logging.getLogger("edl_resource_inventory")


class ExitCode(int, Enum):
    OK = 0
    PARTIAL = 1
    FAILED = 2


def _ensure_src() -> None:
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))


def configure_logging(verbose: int, quiet: bool) -> None:
    if quiet:
        level = logging.WARNING
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else APP_ROOT / path


def _check_mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _count_aws_profiles() -> int:
    config_path = Path.home() / ".aws" / "config"
    if not config_path.is_file():
        return 0
    count = 0
    for line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "[default]" or stripped.startswith("[profile "):
            count += 1
    return count


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def cmd_guide(_args: argparse.Namespace) -> ExitCode:
    readme = APP_ROOT / "README.md"
    if readme.is_file():
        print(readme.read_text(encoding="utf-8"))
    else:
        print("See README.md in this directory.")
    return ExitCode.OK


def cmd_setup(args: argparse.Namespace) -> ExitCode:
    print("\nEDL resource inventory — setup\n")
    venv_path = APP_ROOT / ".venv"
    if args.install:
        if not venv_path.is_dir():
            subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
            print(f"Created virtual environment: {venv_path}")
        venv_python = venv_path / "bin" / "python"
        if not venv_python.is_file():
            venv_python = venv_path / "Scripts" / "python.exe"
        req = APP_ROOT / "requirements.txt"
        subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(venv_python), "-m", "pip", "install", "-r", str(req)])
        print("Dependencies installed (boto3, PyYAML, pytest).")
        print(f"\nActivate, then run doctor:\n  source {venv_path}/bin/activate")
    else:
        print("Run with --install to create .venv and install dependencies.")

    env_file = APP_ROOT / "config" / ".env"
    example = APP_ROOT / "config" / "env.example"
    if not env_file.exists() and example.exists():
        shutil.copy(example, env_file)
        print(f"Created {env_file} from template (optional).")
    resolve_path(DEFAULT_OUTPUT).mkdir(parents=True, exist_ok=True)
    print("\nSetup step complete. Next:")
    print("  1. source .venv/bin/activate")
    print("  2. python edl_resource_inventory.py doctor")
    print("  3. python edl_resource_inventory.py login --all")
    print("  4. python edl_resource_inventory.py profiles --check")
    return ExitCode.OK


def cmd_doctor(_args: argparse.Namespace) -> ExitCode:
    print("\nEDL resource inventory — environment check\n")
    py_ok = sys.version_info >= (3, 9)
    print(f"  [{_check_mark(py_ok)}] Python 3.9+ ({sys.version.split()[0]})")
    deps_ok = True
    for module in ("boto3", "yaml"):
        try:
            __import__(module)
            print(f"  [{_check_mark(True)}] import {module}")
        except ImportError:
            deps_ok = False
            print(f"  [{_check_mark(False)}] import {module} — run setup --install")

    cfg = resolve_path(DEFAULT_CONFIG)
    cfg_ok = cfg.is_file()
    print(f"  [{_check_mark(cfg_ok)}] Inventory config: {cfg}")

    accounts = resolve_path(DEFAULT_ACCOUNTS)
    accounts_ok = accounts.is_file()
    print(f"  [{_check_mark(accounts_ok)}] Account catalog: {accounts}")

    module = APP_ROOT / "infra" / "modules" / "r-edl-resource-inventory" / "main.tf"
    print(f"  [{_check_mark(module.is_file())}] Terraform module: {module}")
    print(f"  [INFO] terraform: {'on PATH' if _which('terraform') else 'not on PATH (needed for apply)'}")
    print(f"  [INFO] terragrunt: {'on PATH' if _which('terragrunt') else 'not on PATH (needed for apply)'}")

    aws_config = Path.home() / ".aws" / "config"
    aws_ok = aws_config.is_file()
    print(f"  [{_check_mark(aws_ok)}] AWS config: {aws_config}")
    print(f"  [INFO] Profiles detected: {_count_aws_profiles() if aws_ok else 0}")

    if cfg_ok:
        try:
            _ensure_src()
            from src.config_loader import load_config
            from src.policy import VIEW_ACTIONS, inventory_policy

            loaded = load_config(cfg, accounts)
            print(f"  [OK] ticket={loaded.ticket} role={loaded.role.name}")
            policy = inventory_policy(partition=loaded.partition, account_id="053381801543")
            assert policy["Statement"][0]["Action"] == VIEW_ACTIONS
            print("  [OK] IAM policy SIDs ViewSpecificResourceGroup + TaggingReadOnly")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] config load: {exc}")
            return ExitCode.FAILED

    resolve_path(DEFAULT_OUTPUT).mkdir(parents=True, exist_ok=True)
    if not (py_ok and deps_ok and cfg_ok and accounts_ok and aws_ok and module.is_file()):
        print("\nFix FAIL items above, then re-run doctor.")
        return ExitCode.FAILED
    print("\nAll checks passed. Run: python edl_resource_inventory.py login --all")
    return ExitCode.OK


def cmd_login(args: argparse.Namespace) -> ExitCode:
    """Refresh AWS SSO for every SSO profile in ~/.aws/config (same as s3-taggings)."""
    _ensure_src()
    from src.sso_login import login_profiles, sso_profile_count

    if not args.all and not args.profiles and not args.only_expired:
        print("Specify --all (all SSO profiles), --only-expired, and/or --profiles NAME …")
        print("Example (same as s3-taggings / tag-audit):")
        print("  python edl_resource_inventory.py login --all")
        return ExitCode.FAILED

    sso_count, total = sso_profile_count()
    print(f"\nEDL SSO login — profiles in ~/.aws/config: {total} total, {sso_count} SSO\n")

    results = login_profiles(
        args.profiles or None,
        only_expired=bool(args.only_expired),
        dry_run=bool(args.dry_run),
    )
    skipped = [row for row in results if row.skipped]
    failed = [row for row in results if not row.ok]
    attempted_n = sum(1 for row in results if row.attempted or "DRY RUN" in row.message)

    for row in results:
        if row.skipped and getattr(args, "verbose", 0) < 1:
            continue
        mark = "OK" if row.ok else "FAIL"
        if row.skipped:
            mark = "SKIP"
        print(f"  [{mark}] {row.profile}: {row.message}")

    print("-" * 50)
    print(f"  SSO login attempted: {attempted_n}")
    print(f"  Skipped:             {len(skipped)}")
    print(f"  Failed:              {len(failed)}")
    if failed:
        return ExitCode.PARTIAL if any(row.ok or row.skipped for row in results) else ExitCode.FAILED
    print("\nNext: python edl_resource_inventory.py profiles --check")
    print("Then:  cd infra/live/r-edl-resource-inventory && AWS_PROFILE=… terragrunt apply")
    return ExitCode.OK


def cmd_profiles(args: argparse.Namespace) -> ExitCode:
    _ensure_src()
    from src.aws_profiles import list_profile_details
    from src.config_loader import load_catalog
    from src.credentials import validate_profile
    from src.identity import lookup_catalog

    details = list_profile_details()
    if not details:
        print("No profiles found in ~/.aws/config")
        return ExitCode.FAILED
    catalog = load_catalog(resolve_path(DEFAULT_ACCOUNTS))
    rows = []
    for item in details:
        catalog_hit = lookup_catalog(catalog, profile=item.name, account_id=item.account_id)
        ok, message = validate_profile(item.name) if args.check else (None, "")
        rows.append(
            {
                "profile": item.name,
                "sso": item.sso,
                "account_id": item.account_id,
                "region": item.region,
                "catalog_name": catalog_hit.name if catalog_hit else "",
                "valid": ok,
                "message": message,
            }
        )
    if args.format == "json":
        print(json.dumps(rows, indent=2))
        return ExitCode.OK
    print(f"Profiles ({len(details)}) — source: ~/.aws/config\n")
    for row in rows:
        kind = "SSO" if row["sso"] else "static"
        extra = row["account_id"] or "—"
        if args.check:
            status = "OK" if row["valid"] else "INVALID"
            print(f"  [{status}] {row['profile']} ({kind}, {extra}) — {row['message']}")
        else:
            print(f"  {row['profile']} ({kind}, {extra}, {row['region'] or '—'})")
    if args.check:
        invalid = sum(1 for row in rows if not row["valid"])
        if invalid:
            print(f"\n{invalid} profile(s) need attention.")
            for row in rows:
                if not row["valid"] and row["sso"]:
                    print(f"  aws sso login --profile {row['profile']}")
            return ExitCode.PARTIAL
    return ExitCode.OK


def cmd_accounts(args: argparse.Namespace) -> ExitCode:
    _ensure_src()
    from src.aws_profiles import list_profile_details
    from src.config_loader import load_catalog

    catalog = load_catalog(resolve_path(DEFAULT_ACCOUNTS))
    details = list_profile_details()
    payload = {
        "role": "r-edl-resource-inventory",
        "live_source": "~/.aws/config",
        "catalog": [{"name": row.name, "account_id": row.account_id, "environment": row.environment} for row in catalog],
        "profiles": [
            {"profile": row.name, "sso": row.sso, "account_id": row.account_id, "region": row.region}
            for row in details
        ],
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return ExitCode.OK
    print("\nRole: r-edl-resource-inventory")
    print("Live Identity Center profiles from ~/.aws/config\n")
    for row in details:
        kind = "SSO" if row.sso else "static"
        print(f"  {row.name:<32} {row.account_id or '—':<16} {kind} {row.region}")
    if not details:
        print("  (none found)")
    print("\nTerragrunt stacks generate one folder per SSO profile.")
    return ExitCode.OK


def _selected_profiles(args: argparse.Namespace, config) -> list[str]:
    from src.aws_profiles import list_aws_profiles, profile_is_sso
    from src.identity import select_profiles

    return select_profiles(
        list_aws_profiles(),
        requested=getattr(args, "profiles", None) or None,
        exclude=config.exclude_profiles,
        sso_only=config.skip_non_sso and not getattr(args, "include_static", False),
        is_sso=profile_is_sso,
    )


def cmd_stacks(args: argparse.Namespace) -> ExitCode:
    _ensure_src()
    from src.config_loader import load_config
    from src.stacks import generate_stacks

    config = load_config(resolve_path(DEFAULT_CONFIG), resolve_path(DEFAULT_ACCOUNTS))
    try:
        selected = _selected_profiles(args, config)
    except ValueError as exc:
        print(f"Profile selection failed: {exc}")
        return ExitCode.FAILED

    if args.stacks_cmd == "generate":
        if not selected:
            print("No SSO profiles selected. Check ~/.aws/config.")
            return ExitCode.FAILED
        paths = generate_stacks(selected, config)
        print(f"Wrote {len(paths)} Terragrunt stack(s) under {LIVE_DIR / 'accounts'}")
        for path in paths:
            print(f"  {path.relative_to(APP_ROOT)}")
        print("\nNext: cd infra/live/accounts && terragrunt run-all plan")
        print("Then:  cd infra/live/accounts && terragrunt run-all apply")
        print("Then:  cd infra/live/accounts && terragrunt run-all output verification")
        return ExitCode.OK

    if not _which("terragrunt"):
        print("terragrunt is not on PATH. Install it, then re-run.")
        return ExitCode.FAILED
    if args.stacks_cmd == "apply" and not getattr(args, "confirm", False):
        print("Apply creates IAM roles in every selected account.")
        print("Re-run with --confirm to proceed.")
        return ExitCode.FAILED

    command = ["terragrunt", "run-all", "plan" if args.stacks_cmd == "plan" else "apply"]
    if args.stacks_cmd == "apply":
        command.append("-auto-approve")
    print(f"Running: {' '.join(command)}  (cwd={LIVE_DIR / 'accounts'})")
    completed = subprocess.run(command, cwd=str(LIVE_DIR / "accounts"), check=False)
    return ExitCode.OK if completed.returncode == 0 else ExitCode.FAILED


def _write_reports(inventory, output_dir: Path) -> dict[str, str]:
    from src.html_report import write_html_reports
    from src.reports import write_data_reports

    output_dir.mkdir(parents=True, exist_ok=True)
    reports = write_data_reports(inventory, output_dir)
    inventory.reports = reports
    reports = write_html_reports(inventory, output_dir)
    inventory.reports = reports
    return reports


def _print_deliverables(inventory) -> None:
    reports = inventory.reports or {}
    print("\n" + "=" * 62)
    print(f"{inventory.ticket} DOCUMENTED RESULTS")
    print("=" * 62)
    if reports.get("index_html"):
        print(f"\n  Start here: {reports['index_html']}\n")
    for key, label in (
        ("executive_html", "Executive summary"),
        ("inventory_csv", "Inventory CSV"),
        ("accounts_csv", "Account summary CSV"),
        ("json", "JSON"),
    ):
        if reports.get(key):
            print(f"  {label:<24} {reports[key]}")
    print("-" * 62)
    print(f"  Tagged resources:      {inventory.resources_total}")
    print(f"  Tag completeness:      {inventory.completeness_pct}%")
    print(f"  Accounts:              {len(inventory.accounts)}")
    print("=" * 62)


def cmd_scan(args: argparse.Namespace) -> ExitCode:
    _ensure_src()
    from src.config_loader import load_config
    from src.credentials import validate_profile
    from src.models import AccountStatus
    from src.reports import inventory_to_dict
    from src.scanner import run_inventory

    config = load_config(resolve_path(Path(args.config)), resolve_path(Path(args.accounts)))
    if args.max_workers:
        config.max_workers = args.max_workers
    output_dir = resolve_path(Path(args.output_dir))
    try:
        selected = _selected_profiles(args, config)
    except ValueError as exc:
        print(f"Profile selection failed: {exc}")
        return ExitCode.FAILED

    print(f"\nEDL Resource Inventory v{__version__}")
    print("=" * 40)
    print(f"Role:               {config.role.name}")
    print(f"Profiles selected:  {len(selected)}")
    print(f"Output directory:   {output_dir}")
    if args.dry_run:
        print("Mode:               DRY RUN\n")
    if not selected:
        print("\nNo profiles selected.")
        return ExitCode.FAILED

    valid: list[str] = []
    print("\nCredential check:")
    for index, profile in enumerate(selected, 1):
        if args.dry_run:
            valid.append(profile)
            print(f"  [{index}/{len(selected)}] DRY  {profile}")
            continue
        ok, message = validate_profile(profile)
        if ok:
            valid.append(profile)
            print(f"  [{index}/{len(selected)}] OK   {profile}")
        else:
            print(f"  [{index}/{len(selected)}] SKIP {profile}: {message}")
    if not valid:
        print("\nNo valid profiles. Run: python edl_resource_inventory.py login --all")
        return ExitCode.FAILED

    inventory = run_inventory(config, profiles=valid, dry_run=bool(args.dry_run))
    if not args.dry_run:
        inventory.reports = _write_reports(inventory, output_dir)

    if args.format == "json":
        print(json.dumps(inventory_to_dict(inventory), indent=2))
    elif not args.dry_run:
        for row in inventory.accounts:
            print(
                f"  [{row.status.value}] {row.profile} {row.account_id or '—'}: "
                f"{row.resources_total} resources, {row.resources_complete} complete"
            )
        _print_deliverables(inventory)

    failed = [row for row in inventory.accounts if row.status in {AccountStatus.DENIED, AccountStatus.ERROR}]
    if not inventory.accounts:
        return ExitCode.FAILED
    if failed and not any(row.status in {AccountStatus.OK, AccountStatus.EMPTY} for row in inventory.accounts):
        return ExitCode.FAILED
    if inventory.resources_missing or failed:
        return ExitCode.PARTIAL
    return ExitCode.OK


def cmd_upload(args: argparse.Namespace) -> ExitCode:
    _ensure_src()
    from botocore.exceptions import BotoCoreError, ClientError
    from src.config_loader import load_config
    from src.s3_uploader import sync_directory_to_s3

    local = resolve_path(Path(args.directory))
    bucket = args.bucket or os.environ.get("S3_BUCKET")
    if not bucket:
        log.error("S3 bucket required (--bucket or S3_BUCKET env)")
        return ExitCode.FAILED
    config = load_config(resolve_path(DEFAULT_CONFIG), resolve_path(DEFAULT_ACCOUNTS))
    prefix = (args.prefix or config.upload_prefix).strip("/")
    print(f"\nSync {local}/ → s3://{bucket}/{prefix}/")
    try:
        count = sync_directory_to_s3(
            local,
            bucket,
            prefix,
            args.region,
            args.profile,
            args.dry_run,
            server_side_encryption=config.server_side_encryption,
        )
    except (ClientError, BotoCoreError, FileNotFoundError, ValueError) as exc:
        log.error("Upload failed: %s", exc)
        return ExitCode.FAILED
    print(f"Done. {count} file(s) {'would be ' if args.dry_run else ''}uploaded.")
    return ExitCode.OK


def cmd_selftest(_args: argparse.Namespace) -> ExitCode:
    tests = APP_ROOT / "tests"
    if not tests.is_dir():
        print("No tests/ directory found.")
        return ExitCode.FAILED
    code = subprocess.call([sys.executable, "-m", "pytest", str(tests), "-q"])
    return ExitCode.OK if code == 0 else ExitCode.FAILED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edl_resource_inventory",
        description="Deploy r-edl-resource-inventory via Terragrunt and inventory tagged resources across SSO accounts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick path (SSO same as s3-taggings, then Terragrunt):\n"
            "  python edl_resource_inventory.py setup --install\n"
            "  python edl_resource_inventory.py doctor\n"
            "  python edl_resource_inventory.py login --all\n"
            "  python edl_resource_inventory.py profiles --check\n"
            "  cd infra/live/r-edl-resource-inventory && AWS_PROFILE=PROFILE terragrunt apply\n"
            "  terragrunt output verification\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-q", "--quiet", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("guide", help="Print README").set_defaults(func=cmd_guide)
    sub.add_parser("doctor", help="Verify Python, AWS config, and Terraform module").set_defaults(func=cmd_doctor)

    setup = sub.add_parser("setup", help="Create venv and install dependencies")
    setup.add_argument("--install", action="store_true")
    setup.set_defaults(func=cmd_setup)

    login = sub.add_parser("login", help="SSO login for all (or selected) profiles — same as s3-taggings")
    login.add_argument("--all", action="store_true", help="Login every SSO profile in ~/.aws/config")
    login.add_argument("--only-expired", action="store_true", help="Only login SSO profiles whose session is invalid")
    login.add_argument("--profiles", nargs="*", help="Limit to these profile names")
    login.add_argument("--dry-run", action="store_true")
    login.set_defaults(func=cmd_login)

    profiles = sub.add_parser("profiles", help="List ~/.aws/config profiles")
    profiles.add_argument("--check", action="store_true", help="Call STS for each profile")
    profiles.add_argument("--format", choices=("text", "json"), default="text")
    profiles.set_defaults(func=cmd_profiles)

    accounts = sub.add_parser("accounts", help="Show live SSO profiles used for Terragrunt")
    accounts.add_argument("--format", choices=("text", "json"), default="text")
    accounts.set_defaults(func=cmd_accounts)

    stacks = sub.add_parser("stacks", help="Generate / plan / apply Terragrunt IAM role stacks")
    stacks.add_argument("--profiles", nargs="*")
    stacks.add_argument("--include-static", action="store_true")
    stacks_sub = stacks.add_subparsers(dest="stacks_cmd", required=True)
    stacks_sub.add_parser("generate", help="Write infra/live/accounts/<profile>/terragrunt.hcl")
    stacks_sub.add_parser("plan", help="terragrunt run-all plan")
    apply = stacks_sub.add_parser("apply", help="terragrunt run-all apply")
    apply.add_argument("--confirm", action="store_true", help="Required — creates IAM roles")
    stacks.set_defaults(func=cmd_stacks)

    scan = sub.add_parser("scan", help="Inventory tagged resources via tag:GetResources")
    scan.add_argument("--config", default=str(DEFAULT_CONFIG))
    scan.add_argument("--accounts", default=str(DEFAULT_ACCOUNTS))
    scan.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    scan.add_argument("--profiles", nargs="*")
    scan.add_argument("--include-static", action="store_true")
    scan.add_argument("--max-workers", type=int, default=None)
    scan.add_argument("--dry-run", action="store_true")
    scan.add_argument("--format", choices=("text", "json"), default="text")
    scan.set_defaults(func=cmd_scan)

    upload = sub.add_parser("upload", help="Sync reports/ to S3")
    upload.add_argument("directory")
    upload.add_argument("--bucket", default=os.environ.get("S3_BUCKET"))
    upload.add_argument("--prefix", default=os.environ.get("S3_PREFIX"))
    upload.add_argument("--region", default=DEFAULT_REGION)
    upload.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    upload.add_argument("--dry-run", action="store_true")
    upload.set_defaults(func=cmd_upload)

    sub.add_parser("selftest", help="Run pytest").set_defaults(func=cmd_selftest)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(args, "verbose", 0), getattr(args, "quiet", False))
    if not getattr(args, "func", None):
        return int(cmd_guide(args))
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        log.warning("Interrupted")
        return int(ExitCode.FAILED)


if __name__ == "__main__":
    sys.exit(main())
