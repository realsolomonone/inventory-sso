#!/usr/bin/env bash
# Check tools needed to authenticate and deploy (Python is optional).

set -euo pipefail
. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/lib.sh"
load_project_env

fail=0
check() {
  _ok=$1
  _label=$2
  if [ "$_ok" -eq 1 ]; then
    echo "  [PASS] $_label"
  else
    echo "  [FAIL] $_label"
    fail=1
  fi
}

echo
echo "inventory-sso — environment check"
echo
print_env_banner
echo

if command -v aws >/dev/null 2>&1; then
  check 1 "aws CLI ($(aws --version 2>&1 | head -n1))"
else
  check 0 "aws CLI — install AWS CLI v2"
fi

if command -v terraform >/dev/null 2>&1; then
  check 1 "terraform ($(terraform version | head -n1))"
else
  check 0 "terraform — required for apply"
fi

if command -v terragrunt >/dev/null 2>&1; then
  check 1 "terragrunt ($(terragrunt --version 2>&1 | head -n1))"
else
  check 0 "terragrunt — required for apply"
fi

_cfg=$(aws_config_path)
if [ -f "$_cfg" ]; then
  _ini_dump
  _total=$(list_profile_names | sed '/^$/d' | wc -l | tr -d ' ')
  _sso=$(list_sso_profiles | sed '/^$/d' | wc -l | tr -d ' ')
  check 1 "AWS config: $_cfg ($_total profiles, $_sso SSO selected)"
else
  check 0 "AWS config missing: $_cfg"
fi

_mod="$ROOT_DIR/infra/modules/r-edl-resource-inventory/main.tf"
if [ -f "$_mod" ]; then
  check 1 "Terraform module: $_mod"
else
  check 0 "Terraform module missing: $_mod"
fi

_env="$ROOT_DIR/config/envs/${ENVIRONMENT}.env"
if [ -f "${ENV_FILE:-$_env}" ] || [ -f "$ROOT_DIR/config/defaults.env" ]; then
  check 1 "project env: ${ENV_FILE:-$_env}"
else
  check 0 "project env missing"
fi

if command -v python3 >/dev/null 2>&1; then
  echo "  [INFO] python3 $(python3 --version 2>&1) — optional (scan reports only)"
else
  echo "  [INFO] python3 not on PATH — optional (scan reports only)"
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "Fix FAIL items, then re-run ./scripts/doctor.sh"
  exit 2
fi
echo "All required checks passed."
echo "Next: ./scripts/sso-login.sh --all"
exit 0
