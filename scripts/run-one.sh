#!/usr/bin/env bash
# Single-account Terragrunt apply using AWS_PROFILE.
# Prefer a generated stack when you have one:
#
#   cd infra/live/accounts/<profile>
#   terragrunt apply
#   terragrunt output verification

set -euo pipefail
. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/lib.sh"
load_project_env

CMD="${1:-}"
YES=0
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-auto-approve) YES=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "${AWS_PROFILE:-}" ]; then
  echo "Set AWS_PROFILE to an IAM Identity Center profile name." >&2
  echo "Example: AWS_PROFILE=edl-addcp-dev-ew ./scripts/run-one.sh apply" >&2
  echo "Or:      cd infra/live/accounts/<profile> && terragrunt apply" >&2
  exit 2
fi

need_cmd terragrunt
require_terraform_15
export AWS_PROFILE AWS_REGION ROLE_NAME
print_env_banner
echo "profile=$AWS_PROFILE"
echo

case "$CMD" in
  plan|apply)
    cd "$ROOT_DIR/infra/live/create"
    ;;
  verify|output)
    cd "$ROOT_DIR/infra/live/verify"
    ;;
  *)
    echo "Usage: AWS_PROFILE=NAME ./scripts/run-one.sh <plan|apply|verify|output> [--yes]" >&2
    exit 2
    ;;
esac

echo "cwd=$(pwd)"
case "$CMD" in
  plan) terragrunt plan ;;
  apply)
    if [ "$YES" -eq 1 ]; then
      terragrunt apply -auto-approve
    else
      terragrunt apply
    fi
    terragrunt output verification || true
    ;;
  verify)
    if [ "$YES" -eq 1 ]; then
      terragrunt apply -auto-approve
    else
      terragrunt apply
    fi
    terragrunt output verification || true
    ;;
  output) terragrunt output verification ;;
esac
