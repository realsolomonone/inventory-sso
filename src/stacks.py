"""Generate Terragrunt stacks for every SSO profile in ~/.aws/config.

Operator path is ./scripts/stacks-generate.sh. This module is kept for tests
and matches the same template placeholders.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .aws_profiles import AwsProfile, describe_profile
from .models import InventoryConfig

APP_ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = APP_ROOT / "infra" / "live"
TEMPLATE = LIVE_DIR / "account.hcl.tmpl"
ACCOUNTS_DIR = LIVE_DIR / "accounts"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def stack_slug(profile: str) -> str:
    slug = _SAFE.sub("-", profile).strip("-")
    return slug or "account"


def render_stack(profile: AwsProfile, config: InventoryConfig) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    region = profile.region or config.home_region
    rg_account = config.role.resource_group_account_id or profile.account_id
    return (
        template.replace("{{profile}}", profile.name)
        .replace("{{region}}", region)
        .replace("{{resource_group_account_id}}", rg_account)
    )


def generate_stacks(
    profiles: list[str],
    config: InventoryConfig,
    *,
    accounts_dir: Path | None = None,
    clean: bool = True,
) -> list[Path]:
    target = accounts_dir or ACCOUNTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    if clean:
        for child in target.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    written: list[Path] = []
    used: set[str] = set()
    for name in profiles:
        info = describe_profile(name)
        slug = stack_slug(name)
        if slug in used:
            slug = f"{slug}-{info.account_id or len(used)}"
        used.add(slug)
        folder = target / slug
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "terragrunt.hcl"
        path.write_text(render_stack(info, config), encoding="utf-8")
        written.append(path)
    return written
