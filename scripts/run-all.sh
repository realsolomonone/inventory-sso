#!/usr/bin/env bash
# Thin wrapper around Terragrunt for every generated account stack.
# Current Terragrunt CLI:
#
#   cd infra/live/accounts
#   terragrunt run --all plan
#   terragrunt run --all apply
#   terragrunt run --all output verification
#
# Older Terragrunt: terragrunt run-all plan  (this script detects both)

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

usage() {
  cat <<EOF
Usage: ./scripts/run-all.sh <plan|apply|output|verify|destroy> [--yes]

Equivalent Terragrunt (current CLI):

  cd infra/live/accounts
  $(tg_all_cmd plan)
  $(tg_all_cmd apply)
  $(tg_all_cmd output verification)

  cd infra/live/verify-accounts
  $(tg_all_cmd apply)
EOF
}

case "$CMD" in
  plan|apply|output|destroy)
    MODE=create
    LIVE_DIR="$ROOT_DIR/infra/live/accounts"
    ;;
  verify)
    MODE=verify
    LIVE_DIR="$ROOT_DIR/infra/live/verify-accounts"
    ;;
  -h|--help|"")
    need_cmd terragrunt
    usage
    exit 2
    ;;
  *)
    need_cmd terragrunt
    usage >&2
    exit 2
    ;;
esac

need_cmd terragrunt
print_env_banner
echo "Terragrunt all-units: $(tg_all_cmd '<command>')"
echo

if [ ! -d "$LIVE_DIR" ] || ! ls -d "$LIVE_DIR"/*/ >/dev/null 2>&1; then
  echo "No Terragrunt stacks in $LIVE_DIR — generating from SSO profiles"
  echo
  if [ "$MODE" = verify ]; then
    "$ROOT_DIR/scripts/stacks-generate.sh" --mode verify
  else
    "$ROOT_DIR/scripts/stacks-generate.sh" --mode create
  fi
fi

if ! ls -d "$LIVE_DIR"/*/ >/dev/null 2>&1; then
  echo "Still no stacks. Add SSO profiles to $(aws_config_path)." >&2
  exit 2
fi

cd "$LIVE_DIR"
echo "cwd=$LIVE_DIR  (run terragrunt from this directory only)"

case "$CMD" in
  plan)
    tg_run_all plan
    ;;
  apply)
    if [ "$YES" -ne 1 ]; then
      echo "Apply creates or updates IAM roles in every selected account."
      echo "Re-run: ./scripts/run-all.sh apply --yes"
      echo "Or:     cd infra/live/accounts && $(tg_all_cmd apply)"
      exit 2
    fi
    tg_run_all apply
    ;;
  output)
    tg_run_all output verification
    ;;
  destroy)
    if [ "$YES" -ne 1 ]; then
      echo "Destroy deletes r-edl-resource-inventory in every selected account."
      echo "Re-run: ./scripts/run-all.sh destroy --yes"
      echo "Or:     cd infra/live/accounts && $(tg_all_cmd destroy)"
      exit 2
    fi
    tg_run_all destroy
    ;;
  verify)
    echo "Verify-role module (no IAM writes)"
    tg_run_all apply
    tg_run_all output verification || true
    ;;
esac
