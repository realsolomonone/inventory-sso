#!/usr/bin/env bash
# Thin wrapper around `terragrunt run-all` for every generated account stack.
# Prefer the Terragrunt commands directly:
#
#   cd infra/live/accounts
#   terragrunt run-all plan
#   terragrunt run-all apply
#   terragrunt run-all output verification

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
  cat <<'EOF'
Usage: ./scripts/run-all.sh <plan|apply|output|verify> [--yes]

Equivalent Terragrunt (preferred):

  cd infra/live/accounts
  terragrunt run-all plan
  terragrunt run-all apply
  terragrunt run-all output verification

  cd infra/live/verify-accounts
  terragrunt run-all apply
EOF
}

case "$CMD" in
  plan|apply|output)
    MODE=create
    LIVE_DIR="$ROOT_DIR/infra/live/accounts"
    ;;
  verify)
    MODE=verify
    LIVE_DIR="$ROOT_DIR/infra/live/verify-accounts"
    ;;
  -h|--help|"")
    usage
    exit 2
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

need_cmd terragrunt
print_env_banner
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
    echo "Running: terragrunt run-all plan --terragrunt-non-interactive"
    terragrunt run-all plan --terragrunt-non-interactive
    ;;
  apply)
    if [ "$YES" -ne 1 ]; then
      echo "Apply creates or updates IAM roles in every selected account."
      echo "Re-run: ./scripts/run-all.sh apply --yes"
      echo "Or:     cd infra/live/accounts && terragrunt run-all apply"
      exit 2
    fi
    echo "Running: terragrunt run-all apply -auto-approve --terragrunt-non-interactive"
    terragrunt run-all apply -auto-approve --terragrunt-non-interactive
    ;;
  output)
    echo "Running: terragrunt run-all output verification --terragrunt-non-interactive"
    terragrunt run-all output verification --terragrunt-non-interactive
    ;;
  verify)
    echo "Running: terragrunt run-all apply (verify-role module, no IAM writes)"
    if [ "$YES" -eq 1 ]; then
      terragrunt run-all apply -auto-approve --terragrunt-non-interactive
    else
      terragrunt run-all apply --terragrunt-non-interactive
    fi
    terragrunt run-all output verification --terragrunt-non-interactive || true
    ;;
esac
