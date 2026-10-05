"""Normalize, validate, and score EDL project tags.

Adapted from ~/workspace/s3-taggings/src/tags.py.
"""

from __future__ import annotations

import re

from .models import TagHealth, TagIssue, TagSpec


def _norm(value: object) -> str:
    return "" if value is None else str(value).strip()


def resolve_tag(tags: dict[str, str], spec: TagSpec) -> str:
    candidates = (spec.key, *spec.aliases)
    for key in candidates:
        if key in tags and _norm(tags[key]):
            return _norm(tags[key])
    lowered = {key.lower(): value for key, value in tags.items()}
    for key in candidates:
        hit = lowered.get(key.lower())
        if _norm(hit):
            return _norm(hit)
    return ""


def extract_expected(tags: dict[str, str], specs: list[TagSpec]) -> dict[str, str]:
    return {spec.key: resolve_tag(tags, spec) for spec in specs}


def extra_tags(tags: dict[str, str], specs: list[TagSpec]) -> dict[str, str]:
    known: set[str] = set()
    for spec in specs:
        known.add(spec.key.lower())
        known.update(alias.lower() for alias in spec.aliases)
    return {key: value for key, value in tags.items() if key.lower() not in known}


def collect_issues(expected: dict[str, str], specs: list[TagSpec]) -> list[TagIssue]:
    issues: list[TagIssue] = []
    for spec in specs:
        value = _norm(expected.get(spec.key))
        if not value:
            issues.append(
                TagIssue(
                    key=spec.key,
                    kind="missing",
                    current="",
                    hint=spec.hint,
                    example=spec.example,
                    reason="Required tag is missing or empty",
                )
            )
            continue
        reason = ""
        if spec.allowed_values and value not in spec.allowed_values:
            reason = f"Must be one of: {', '.join(spec.allowed_values)}"
        elif spec.pattern and re.fullmatch(spec.pattern, value) is None:
            reason = spec.hint or f"Does not match {spec.pattern}"
        if reason:
            issues.append(
                TagIssue(
                    key=spec.key,
                    kind="invalid",
                    current=value,
                    hint=spec.hint,
                    example=spec.example,
                    reason=reason,
                )
            )
    return issues


def score_tags(
    expected: dict[str, str],
    specs: list[TagSpec],
    *,
    tag_error: str = "",
    issues: list[TagIssue] | None = None,
) -> tuple[TagHealth, float]:
    if tag_error:
        return TagHealth.ERROR, 0.0
    if not specs:
        return TagHealth.COMPLETE, 100.0
    found = collect_issues(expected, specs) if issues is None else issues
    valid = len(specs) - len(found)
    pct = round(100.0 * valid / len(specs), 1)
    if valid == len(specs):
        return TagHealth.COMPLETE, 100.0
    if valid == 0:
        return TagHealth.UNTAGGED, 0.0
    if found and all(item.kind == "invalid" for item in found):
        return TagHealth.INVALID, pct
    return TagHealth.PARTIAL, pct
