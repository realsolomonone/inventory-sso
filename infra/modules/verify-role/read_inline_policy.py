#!/usr/bin/env python3
"""Terraform external data helper: read an IAM inline role policy via AWS CLI.

stdin:  {"role_name","policy_name","profile","region"}
stdout: {"found","policy","error"}  (all strings)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def _out(found: str, policy: str, error: str = "") -> None:
    json.dump({"found": found, "policy": policy, "error": error[:400]}, sys.stdout)


def main() -> int:
    query = json.load(sys.stdin)
    role_name = query.get("role_name") or ""
    policy_name = query.get("policy_name") or ""
    env = os.environ.copy()
    profile = query.get("profile") or ""
    region = query.get("region") or ""
    if profile:
        env["AWS_PROFILE"] = profile
    if region:
        env["AWS_REGION"] = region
        env["AWS_DEFAULT_REGION"] = region

    cmd = [
        "aws",
        "iam",
        "get-role-policy",
        "--role-name",
        role_name,
        "--policy-name",
        policy_name,
        "--output",
        "json",
    ]
    try:
        completed = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        _out("false", "{}", "aws CLI not found")
        return 0

    if completed.returncode != 0:
        _out("false", "{}", (completed.stderr or completed.stdout or f"exit {completed.returncode}").strip())
        return 0

    try:
        payload = json.loads(completed.stdout)
        doc = payload.get("PolicyDocument", {})
        _out("true", json.dumps(doc), "")
    except json.JSONDecodeError as exc:
        _out("false", "{}", str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
