#!/usr/bin/env bash
# Check tools needed to authenticate (AWS CLI) and deploy (Terragrunt).

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
echo "inventory-sso — Terragrunt environment check"
echo
print_env_banner
echo

if command -v aws >/dev/null 2>&1; then
  check 1 "aws CLI ($(aws --version 2>&1 | head -n1))"
else
  check 0 "aws CLI — required for SSO login"
fi

if command -v terragrunt >/dev/null 2>&1; then
  check 1 "terragrunt ($(terragrunt --version 2>&1 | head -n1))"
else
  check 0 "terragrunt — required for plan/apply across accounts"
fi

if _tf=$(discover_terraform_15); then
  check 1 "terraform $("$_tf" version 2>/dev/null | head -n1) ($_tf) — Terragrunt uses scripts/terraform-shim"
else
  _def=$(command -v terraform 2>/dev/null || true)
  _ver=""
  [ -n "$_def" ] && _ver=$("$_def" version 2>/dev/null | head -n1)
  check 0 "terraform >= 1.5.0 not found (PATH ${_def:-none} ${_ver} — iebcloud default is often v0.12.31). module load terraform/1.5 or export TG_TF_PATH=..."
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

_root="$ROOT_DIR/infra/live/root.hcl"
if [ -f "$_root" ]; then
  check 1 "Terragrunt root: $_root"
else
  check 0 "Terragrunt root missing: $_root"
fi

_mod="$ROOT_DIR/infra/modules/r-edl-resource-inventory/main.tf"
if [ -f "$_mod" ]; then
  check 1 "IAM module (used by Terragrunt): $_mod"
else
  check 0 "IAM module missing: $_mod"
fi

_env="$ROOT_DIR/config/envs/${ENVIRONMENT}.env"
if [ -f "${ENV_FILE:-$_env}" ] || [ -f "$ROOT_DIR/config/defaults.env" ]; then
  check 1 "project env: ${ENV_FILE:-$_env}"
else
  check 0 "project env missing"
fi

echo "  [INFO] python3 is optional (scan reports only)"

echo
if [ "$fail" -ne 0 ]; then
  echo "Fix FAIL items, then re-run ./scripts/doctor.sh"
  exit 2
fi
echo "All required checks passed."
echo "Next: ./scripts/sso-login.sh --all"
echo "Then: ./scripts/stacks-generate.sh"
echo "Then: cd infra/live/accounts && $(tg_all_cmd apply)"
exit 0
