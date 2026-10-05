#!/usr/bin/env bash
# Plan / apply / verify / output Terragrunt stacks for every generated account.
#
#   ./scripts/run-all.sh plan
#   ./scripts/run-all.sh apply --yes
#   ./scripts/run-all.sh output
#   ./scripts/run-all.sh verify
#   ENVIRONMENT=commercial ./scripts/run-all.sh apply --yes

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

  plan     terragrunt run-all plan   (create stacks)
  apply    terragrunt run-all apply  (create + verify IAM; requires --yes)
  output   terragrunt run-all output verification
  verify   data-only verify stacks (infra/live/verify-accounts)

Generate stacks first with ./scripts/stacks-generate.sh (verify uses --mode verify).
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
  echo "No stacks in $LIVE_DIR"
  echo "Generating from SSO profiles…"
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
echo "cwd=$LIVE_DIR"

case "$CMD" in
  plan)
    echo "Running: terragrunt run-all plan"
    terragrunt run-all plan
    ;;
  apply)
    if [ "$YES" -ne 1 ]; then
      echo "Apply creates or updates IAM roles in every selected account."
      echo "Re-run: ./scripts/run-all.sh apply --yes"
      exit 2
    fi
    echo "Running: terragrunt run-all apply -auto-approve"
    terragrunt run-all apply -auto-approve
    ;;
  output)
    echo "Running: terragrunt run-all output verification"
    terragrunt run-all output verification
    ;;
  verify)
    echo "Running: terragrunt run-all apply (verify-role, no IAM writes)"
    if [ "$YES" -eq 1 ]; then
      terragrunt run-all apply -auto-approve
    else
      terragrunt run-all apply
    fi
    terragrunt run-all output verification || true
    ;;
esac
