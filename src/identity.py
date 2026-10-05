"""Profile selection and catalog lookup — same identity model as s3-taggings."""

from __future__ import annotations

from collections.abc import Callable

from .models import CatalogAccount


def select_profiles(
    all_profiles: list[str],
    *,
    requested: list[str] | None,
    exclude: list[str] | None,
    sso_only: bool,
    is_sso: Callable[[str], bool],
) -> list[str]:
    names = list(requested or all_profiles)
    skip = set(exclude or [])
    selected: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in skip or name in seen:
            continue
        if sso_only and not is_sso(name):
            continue
        selected.append(name)
        seen.add(name)
    missing = [name for name in (requested or []) if name not in all_profiles]
    if missing:
        raise ValueError("Unknown profile(s): " + ", ".join(missing))
    return selected


def lookup_catalog(
    catalog: list[CatalogAccount],
    *,
    profile: str,
    account_id: str,
) -> CatalogAccount | None:
    profile_l = profile.lower()
    for entry in catalog:
        names = [entry.name, *entry.aliases]
        if profile_l and any(profile_l == name.lower() for name in names if name):
            return entry
    if account_id:
        for entry in catalog:
            if entry.account_id == account_id:
                return entry
    return None
