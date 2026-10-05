#!/usr/bin/env python3
"""
EDL resource inventory — production CLI.

Preferred operator path is shell (no Python required for SSO or Terragrunt):

  ./scripts/sso-login.sh --all
  ./scripts/run-all.sh apply --yes

This Python CLI wraps those scripts and still provides optional scan/upload.
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


def _run_script(name: str, extra: Sequence[str] | None = None) -> ExitCode:
    script = APP_ROOT / "scripts" / name
    cmd = ["bash", str(script), *(extra or ())]
    print(f"running: {' '.join(cmd)}")
    completed = subprocess.run(cmd, check=False)
    if completed.returncode == 0:
        return ExitCode.OK
    if completed.returncode == 1:
        return ExitCode.PARTIAL
    return ExitCode.FAILED


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
    print("  1. ./scripts/doctor.sh")
    print("  2. ./scripts/sso-login.sh --all")
    print("  3. ./scripts/sso-profiles.sh --check")
    print("  4. ./scripts/run-all.sh apply --yes")
    return ExitCode.OK


def cmd_doctor(_args: argparse.Namespace) -> ExitCode:
    return _run_script("doctor.sh")


def cmd_login(args: argparse.Namespace) -> ExitCode:
    """Refresh AWS SSO via scripts/sso-login.sh (no Python SSO logic)."""
    extra: list[str] = []
    if args.all:
        extra.append("--all")
    if args.only_expired:
        extra.append("--only-expired")
    if args.dry_run:
        extra.append("--dry-run")
    if args.profiles:
        extra.append("--profiles")
        extra.extend(args.profiles)
    if not extra:
        print("Specify --all, --only-expired, and/or --profiles NAME …")
        print("Preferred: ./scripts/sso-login.sh --all")
        return ExitCode.FAILED
    return _run_script("sso-login.sh", extra)


def cmd_profiles(args: argparse.Namespace) -> ExitCode:
    extra: list[str] = []
    if args.check:
        extra.append("--check")
    if args.format == "json":
        extra.append("--json")
    return _run_script("sso-profiles.sh", extra)


def cmd_accounts(args: argparse.Namespace) -> ExitCode:
    extra = ["--sso-only"]
    if args.format == "json":
        extra.append("--json")
    return _run_script("sso-profiles.sh", extra)


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
    if args.stacks_cmd == "generate":
        return _run_script("stacks-generate.sh")
    if args.stacks_cmd == "plan":
        return _run_script("run-all.sh", ["plan"])
    extra = ["apply"]
    if getattr(args, "confirm", False):
        extra.append("--yes")
    return _run_script("run-all.sh", extra)


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
            "Quick path (shell + Terragrunt; Python is optional):\n"
            "  ./scripts/doctor.sh\n"
            "  ./scripts/sso-login.sh --all\n"
            "  ./scripts/sso-profiles.sh --check\n"
            "  ./scripts/run-all.sh apply --yes\n"
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
