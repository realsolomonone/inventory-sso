"""Load AWS CLI profiles from ~/.aws/config.

Adapted from ~/workspace/s3-taggings/src/aws_profiles.py so this repo is
standalone and reuses the same Identity Center detection rules.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AwsProfile:
    name: str
    sso: bool
    account_id: str
    region: str
    role_name: str
    session: str


def _config_path(config_path: Path | None) -> Path:
    return config_path or Path.home() / ".aws" / "config"


def _section_name(profile: str) -> str:
    return "default" if profile == "default" else f"profile {profile}"


def _load_config(config_path: Path | None = None) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    path = _config_path(config_path)
    if path.exists():
        parser.read(path)
    return parser


def list_aws_profiles(config_path: Path | None = None) -> list[str]:
    parser = _load_config(config_path)
    profiles: list[str] = []

    if parser.has_section("default"):
        profiles.append("default")

    for section in parser.sections():
        if section.startswith("profile "):
            profiles.append(section.removeprefix("profile "))

    return profiles


def profile_is_sso(profile: str, config_path: Path | None = None) -> bool:
    """True if the profile is configured for AWS SSO (IAM Identity Center)."""
    parser = _load_config(config_path)
    section = _section_name(profile)

    if not parser.has_section(section):
        return False

    options = set(parser.options(section))

    if "sso_start_url" in options and "sso_region" in options:
        return True

    if "sso_session" in options:
        session_name = parser.get(section, "sso_session")
        session_section = f"sso-session {session_name}"
        if parser.has_section(session_section):
            session_opts = set(parser.options(session_section))
            return "sso_start_url" in session_opts and "sso_region" in session_opts

    return False


def list_sso_profiles(config_path: Path | None = None) -> list[str]:
    return [p for p in list_aws_profiles(config_path) if profile_is_sso(p, config_path)]


def list_non_sso_profiles(config_path: Path | None = None) -> list[str]:
    return [p for p in list_aws_profiles(config_path) if not profile_is_sso(p, config_path)]


def describe_profile(profile: str, config_path: Path | None = None) -> AwsProfile:
    parser = _load_config(config_path)
    section = _section_name(profile)
    account_id = ""
    region = ""
    role_name = ""
    session = ""
    if parser.has_section(section):
        account_id = parser.get(section, "sso_account_id", fallback="").strip()
        region = parser.get(section, "region", fallback="").strip()
        role_name = parser.get(section, "sso_role_name", fallback="").strip()
        session = parser.get(section, "sso_session", fallback="").strip()
    return AwsProfile(
        name=profile,
        sso=profile_is_sso(profile, config_path),
        account_id=account_id,
        region=region,
        role_name=role_name,
        session=session,
    )


def list_profile_details(config_path: Path | None = None) -> list[AwsProfile]:
    return [describe_profile(name, config_path) for name in list_aws_profiles(config_path)]
