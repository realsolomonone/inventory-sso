from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _aws_config(tmp_path: Path) -> Path:
    aws = tmp_path / ".aws"
    aws.mkdir()
    cfg = aws / "config"
    cfg.write_text(
        "\n".join(
            [
                "[default]",
                "region = us-east-1",
                "",
                "[profile edl-uat]",
                "sso_start_url = https://example.awsapps.com/start",
                "sso_region = us-gov-east-1",
                "sso_account_id = 111111111111",
                "sso_role_name = Admin",
                "region = us-gov-east-1",
                "",
                "[profile edl-dev]",
                "sso_start_url = https://example.awsapps.com/start",
                "sso_region = us-gov-east-1",
                "sso_account_id = 222222222222",
                "sso_role_name = Admin",
                "region = us-gov-east-1",
                "",
                "[profile static-keys]",
                "region = us-east-1",
                "",
                "[profile other-org]",
                "sso_start_url = https://other.awsapps.com/start",
                "sso_region = us-east-1",
                "sso_account_id = 333333333333",
                "sso_role_name = Admin",
                "region = us-east-1",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _run(args: list[str], tmp_path: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["AWS_CONFIG_FILE"] = str(tmp_path / ".aws" / "config")
    env.pop("PROFILE_PREFIX", None)
    env.pop("SSO_START_URL", None)
    env.pop("EXCLUDE_PROFILES", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(args, cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)


def test_sso_login_all_dry_run_groups_same_start_url(tmp_path: Path):
    _aws_config(tmp_path)
    completed = _run(["bash", str(SCRIPTS / "sso-login.sh"), "--all", "--dry-run"], tmp_path)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "aws sso login --profile edl-uat" in completed.stdout or "aws sso login --profile edl-dev" in completed.stdout
    assert "same SSO session already logged in" in completed.stdout
    assert "static-keys" not in completed.stdout
    assert "SSO login attempted: 2" in completed.stdout
    assert "./scripts/sso-profiles.sh --check" in completed.stdout


def test_sso_login_per_profile_dry_run(tmp_path: Path):
    _aws_config(tmp_path)
    completed = _run(
        ["bash", str(SCRIPTS / "sso-login.sh"), "--all", "--per-profile", "--dry-run"],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "aws sso login --profile edl-uat" in completed.stdout
    assert "aws sso login --profile edl-dev" in completed.stdout
    assert "aws sso login --profile other-org" in completed.stdout
    assert "SSO login attempted: 3" in completed.stdout


def test_sso_login_prefix_filter(tmp_path: Path):
    _aws_config(tmp_path)
    completed = _run(
        ["bash", str(SCRIPTS / "sso-login.sh"), "--all", "--dry-run"],
        tmp_path,
        extra_env={"PROFILE_PREFIX": "edl-"},
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "aws sso login --profile other-org" not in completed.stdout


def test_lib_parses_sso_profiles(tmp_path: Path):
    _aws_config(tmp_path)
    helper = r"""
set -euo pipefail
. scripts/lib.sh
load_project_env
_ini_dump
if is_sso_profile static-keys; then exit 1; fi
is_sso_profile edl-uat
test "$(profile_account_id edl-uat)" = "111111111111"
test "$(profile_region edl-uat)" = "us-gov-east-1"
test "$(stack_slug "profile name")" = "profile-name"
"""
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["AWS_CONFIG_FILE"] = str(tmp_path / ".aws" / "config")
    completed = subprocess.run(
        ["bash", "-c", helper],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout

    template = (ROOT / "infra" / "live" / "account.hcl.tmpl").read_text(encoding="utf-8")
    text = (
        template.replace("{{profile}}", "edl-uat")
        .replace("{{region}}", "us-gov-east-1")
        .replace("{{resource_group_account_id}}", "111111111111")
    )
    assert 'aws_profile               = "edl-uat"' in text
    assert 'include "root"' in text
    assert "include.root.locals" not in text
    assert "111111111111" in text
    assert "{{profile}}" not in text
