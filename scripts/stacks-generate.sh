#!/usr/bin/env bash
# Write one Terragrunt stack per matching SSO profile.
#
#   ./scripts/stacks-generate.sh
#   ./scripts/stacks-generate.sh --mode verify
#   ENVIRONMENT=commercial ./scripts/stacks-generate.sh

set -euo pipefail
. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/lib.sh"
load_project_env

MODE=create
CLEAN=1

while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE=$2; shift 2 ;;
    --no-clean) CLEAN=0; shift ;;
    -h|--help)
      echo "Usage: ./scripts/stacks-generate.sh [--mode create|verify] [--no-clean]"
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$MODE" in
  create)
    ACCOUNTS_DIR="$ROOT_DIR/infra/live/accounts"
    TEMPLATE="$ROOT_DIR/infra/live/account.hcl.tmpl"
    ;;
  verify)
    ACCOUNTS_DIR="$ROOT_DIR/infra/live/verify-accounts"
    TEMPLATE="$ROOT_DIR/infra/live/account-verify.hcl.tmpl"
    ;;
  *)
    echo "mode must be create or verify" >&2
    exit 2
    ;;
esac

if [ ! -f "$TEMPLATE" ]; then
  echo "Template missing: $TEMPLATE" >&2
  exit 2
fi

if [ ! -f "$(aws_config_path)" ]; then
  echo "No AWS config at $(aws_config_path)" >&2
  exit 2
fi

_ini_dump
print_env_banner
echo

profiles=$(list_sso_profiles)
if [ -z "$profiles" ]; then
  echo "No SSO profiles selected. Add Identity Center profiles to $(aws_config_path)." >&2
  exit 2
fi

mkdir -p "$ACCOUNTS_DIR"
if [ "$CLEAN" -eq 1 ]; then
  for child in "$ACCOUNTS_DIR"/*; do
    [ -e "$child" ] || continue
    case "$(basename "$child")" in
      .gitkeep) continue ;;
    esac
    rm -rf "$child"
  done
fi

written=0
used_slugs=""

slug_taken() {
  case " $used_slugs " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

OLDIFS=$IFS
IFS='
'
# shellcheck disable=SC2086
set -- $profiles
IFS=$OLDIFS

for _p in "$@"; do
  [ -n "$_p" ] || continue
  slug=$(stack_slug "$_p")
  [ -n "$slug" ] || slug=account
  if slug_taken "$slug"; then
    _acct=$(profile_account_id "$_p")
    slug="${slug}-${_acct:-$written}"
  fi
  used_slugs="${used_slugs} ${slug}"
  dest="$ACCOUNTS_DIR/$slug"
  mkdir -p "$dest"

  _region=$(profile_region "$_p")
  _acct=$(profile_account_id "$_p")
  _rg="$RESOURCE_GROUP_ACCOUNT_ID"
  [ -n "$_rg" ] || _rg="$_acct"

  awk \
    -v profile="$_p" \
    -v region="$_region" \
    -v rg="$_rg" \
    '
      {
        gsub(/\{\{profile\}\}/, profile)
        gsub(/\{\{region\}\}/, region)
        gsub(/\{\{resource_group_account_id\}\}/, rg)
        print
      }
    ' "$TEMPLATE" > "$dest/terragrunt.hcl"
  written=$((written + 1))
  echo "  wrote infra/live/$(basename "$ACCOUNTS_DIR")/$slug/terragrunt.hcl  (profile=$_p)"
done

echo
echo "Wrote $written Terragrunt stack(s) under $ACCOUNTS_DIR"
if [ "$MODE" = create ]; then
  echo "Next: cd infra/live/accounts && terragrunt run-all plan"
  echo "Then: cd infra/live/accounts && terragrunt run-all apply"
else
  echo "Next: cd infra/live/verify-accounts && terragrunt run-all apply"
  echo "Then: cd infra/live/verify-accounts && terragrunt run-all output verification"
fi
exit 0
