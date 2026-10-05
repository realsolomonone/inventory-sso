"""SSO login helpers for hosts with many ~/.aws/config profiles.

Adapted from ~/workspace/s3-taggings/src/sso_login.py
(python edl_s3_tag_inventory.py login --all).
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

from .aws_profiles import list_aws_profiles, list_sso_profiles, profile_is_sso
from .credentials import validate_profile

logger = logging.getLogger(__name__)


@dataclass
class LoginResult:
    profile: str
    attempted: bool
    ok: bool
    skipped: bool
    message: str


def login_profiles(
    profiles: list[str] | None = None,
    *,
    only_expired: bool = False,
    dry_run: bool = False,
) -> list[LoginResult]:
    """
    Run `aws sso login` for SSO profiles in ~/.aws/config.

    Static / access-key profiles are skipped (they do not use SSO).
    Same contract as ~/workspace/s3-taggings.
    """
    all_profiles = profiles or list_aws_profiles()
    results: list[LoginResult] = []

    for profile in all_profiles:
        if not profile_is_sso(profile):
            results.append(
                LoginResult(
                    profile=profile,
                    attempted=False,
                    ok=True,
                    skipped=True,
                    message="Not an SSO profile (static/role credentials) — skipped",
                )
            )
            continue

        if only_expired:
            valid, message = validate_profile(profile)
            if valid:
                results.append(
                    LoginResult(
                        profile=profile,
                        attempted=False,
                        ok=True,
                        skipped=True,
                        message=f"Session already valid — {message}",
                    )
                )
                continue

        command = ["aws", "sso", "login"]
        if profile != "default":
            command.extend(["--profile", profile])
        if dry_run:
            results.append(
                LoginResult(
                    profile=profile,
                    attempted=False,
                    ok=True,
                    skipped=False,
                    message=f"DRY RUN: {' '.join(command)}",
                )
            )
            continue

        logger.info("SSO login: %s", " ".join(command))
        try:
            completed = subprocess.run(command, check=False)
            if completed.returncode == 0:
                results.append(
                    LoginResult(
                        profile=profile,
                        attempted=True,
                        ok=True,
                        skipped=False,
                        message="SSO login succeeded",
                    )
                )
            else:
                results.append(
                    LoginResult(
                        profile=profile,
                        attempted=True,
                        ok=False,
                        skipped=False,
                        message=f"aws sso login failed (exit {completed.returncode})",
                    )
                )
        except FileNotFoundError:
            results.append(
                LoginResult(
                    profile=profile,
                    attempted=True,
                    ok=False,
                    skipped=False,
                    message="AWS CLI not found — install awscli v2 on this server",
                )
            )
            break
        except OSError as exc:
            results.append(
                LoginResult(
                    profile=profile,
                    attempted=True,
                    ok=False,
                    skipped=False,
                    message=str(exc),
                )
            )

    return results


def sso_profile_count() -> tuple[int, int]:
    """Return (sso_count, total_count)."""
    total = list_aws_profiles()
    sso = list_sso_profiles()
    return len(sso), len(total)
